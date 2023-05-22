#!/usr/bin/env python3

from collections import namedtuple
from dataclasses import dataclass, field
import argparse
import os
import re
import subprocess
import sys

Namespace = namedtuple("Namespace", "name module")

@dataclass
class Module:
    unstable: bool
    cfgs: list = field(default_factory=list)

# Parse arguments

parser = argparse.ArgumentParser(
    description="Generate a std compatibility module"
)
parser.add_argument("--src", help=(
    "Specify the location of the rust source code. The default is "
    "`$(rustc --print sysroot)/lib/rustlib/src/rust/library`"
))
args = parser.parse_args()

if args.src is None:
    output = subprocess.run(["rustc", "--print", "sysroot"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    args.src = os.path.join(output.stdout.decode("utf-8").strip(),
                            "lib", "rustlib", "src", "rust", "library")


# Read files

modules_regex = re.compile(
    r"^(?:\S.*)?pub\s+(?:mod\s+|use\s+(?:[a-zA-Z_][a-zA-Z0-9_]*::)*)"
    r"([a-zA-Z_][a-zA-Z0-9_]*);",
    re.MULTILINE
)


def modules(crate):
    """
    Return a dictionary of all modules and whether they appear unstable or not.
    """
    root = os.path.join(args.src, crate, "src")
    lib = os.path.join(root, "lib.rs")
    with open(lib) as f:
        contents = f.read()

    modules = dict()
    for match in modules_regex.finditer(contents):
        module = match.group(1)
        unstable = False

        path = os.path.join(root, module + ".rs")
        if not os.path.isfile(path):
            path = os.path.join(root, module, "mod.rs")
        try:
            with open(path, "r", encoding="utf8") as f:
                unstable = "#![unstable" in f.read()
                if unstable:
                    print(
                        f"Module '{module}' from '{crate}' appears unstable",
                        file=sys.stderr
                    )
        except OSError as e:
            print(e, file=sys.stderr)
            pass

        modules[module] = Module(unstable)
    return modules


def generate(module, *namespaces):
    """
    Generate code for any module, given its name and which namespaces it appears
    under and whether it's unstable or not.
    """
    out = f"pub mod {module} {{\n"

    if module == "prelude":
        return None

    for namespace in namespaces:
        out += "    "

        cfgs = []
        if namespace.name != "core":
            cfgs.append(f"feature = \"{namespace.name}\"")
        if namespace.module.unstable:
            cfgs.append("feature = \"unstable\"")
        cfgs += namespace.module.cfgs

        if len(cfgs) == 1:
            out += f"#[cfg({cfgs[0]})] "
        elif len(cfgs) > 1:
            out += "#[cfg(all(" + ", ".join(cfgs) + "))] "

        out += f"pub use __{namespace.name}::{module}::*;\n"

    if module == "collections":
        prefix = (
            "    #[cfg(all("
            "feature = \"alloc\", "
            "feature = \"compat_hash\""
            "))] pub use hashbrown::"
        )
        out += (
            prefix + "HashMap;\n" +
            prefix + "HashSet;\n"
        )
    elif module == "sync":
        prefix = (
            "    #[cfg(all("
            "feature = \"alloc\", "
            "feature = \"compat_sync\""
            "))] pub use spin::"
        )
        out += (
            prefix + "Mutex;\n" +
            prefix + "MutexGuard;\n" +
            prefix + "Once;\n" +
            prefix + "RwLock;\n" +
            prefix + "RwLockReadGuard;\n" +
            prefix + "RwLockWriteGuard;\n"
        )
    elif module == "ffi":
        prefix = (
            "    #[cfg(all("
            "feature = \"alloc\", "
            "feature = \"compat_cstr\""
            "))] pub use cstr_core::"
        )
        out += (
            prefix + "CStr;\n"
        )

    out += "}"
    return out


# Main logic

core = modules("core")
alloc = modules("alloc")

# Module overrides
core["async_iter"].unstable = True
alloc["sync"].cfgs.append("not(target_os = \"none\")")
alloc["task"].cfgs.append("not(target_os = \"none\")")

generated = {}

core_keys = set(core.keys())
alloc_keys = set(alloc.keys())

# Appearing in both
for module in core_keys & alloc_keys:
    generated[module] = generate(
        module,
        Namespace("core", core[module]),
        Namespace("alloc", alloc[module]),
    )

# Only in core
for module in core_keys - alloc_keys:
    generated[module] = generate(
        module,
        Namespace("core", core[module]),
    )

# Only in alloc
for module in alloc_keys - core_keys:
    generated[module] = generate(
        module,
        Namespace("alloc", alloc[module]),
    )

# Complete module overrides

generated["compat_guard_unwrap"] = """
#[cfg(feature = "compat_guard_unwrap")]
pub mod compat_guard_unwrap {
    pub trait UnwrapExt: Sized {
        fn unwrap(self) -> Self { self }
    }
    #[cfg(all(feature = "alloc", feature = "compat_sync"))] impl<'a, T: ?Sized> UnwrapExt for super::sync::MutexGuard<'a, T> {}
    #[cfg(all(feature = "alloc", feature = "compat_sync"))] impl<'a, T: ?Sized> UnwrapExt for super::sync::RwLockReadGuard<'a, T> {}
    #[cfg(all(feature = "alloc", feature = "compat_sync"))] impl<'a, T: ?Sized> UnwrapExt for super::sync::RwLockWriteGuard<'a, T> {}
}"""

generated["prelude"] = """pub mod prelude {
    pub mod v1 {
        // Prelude
        pub use __core::prelude::rust_2021::*;
        #[cfg(all(feature = "alloc", not(feature = "unstable")))]
        pub use __alloc::{
            // UNSTABLE: slice::SliceConcatExt,
        };

        // Other imports
        #[cfg(feature = "alloc")]
        pub use __alloc::{format, vec, vec::Vec, string::String, string::ToString, borrow::ToOwned, boxed::Box};
        #[cfg(feature = "compat_macros")]
        pub use crate::{print, println, eprint, eprintln, dbg};
        #[cfg(feature = "compat_guard_unwrap")] pub use crate::compat_guard_unwrap::UnwrapExt as __CompatGuardUnwrapExt;
    }
}"""

generated["os"] = """pub mod os {
    pub mod raw {
        pub use __core::ffi::c_void;
        #[cfg(feature = "compat_osraw")] pub use libc::{c_char, c_double, c_float, c_int, c_long, c_longlong, c_schar, c_short, c_uchar, c_uint, c_ulong, c_ulonglong, c_ushort};
    }
}"""

generated["path"] = """pub mod path {
    #[cfg(feature = "compat_path")] pub use unix_path::*;
}"""

print("""//! Generated by generate.py located at the repository root
//! ./generate.py > src/generated.rs""")
for module in sorted(generated.items(), key=lambda i: i[0]):
    print(module[1])
