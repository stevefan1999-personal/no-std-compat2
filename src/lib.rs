#![cfg_attr(all(doc, CHANNEL_NIGHTLY), feature(doc_cfg, doc_auto_cfg))]
#![no_std]
#![cfg_attr(
    all(not(feature = "std"), feature = "unstable"),
    feature(
        core_intrinsics,
        core_panic,
        once_cell,
        unicode_internals,
        async_iterator,
        ip_in_core,
        generic_assert_internals,
        error_in_core,
        cfg_version
    )
)]
#![cfg_attr(
    all(not(feature = "std"), feature = "alloc", feature = "unstable"),
    feature(raw_vec_internals)
)]

//! ## Feature flags
#![doc = document_features::document_features!(feature_label = r#"<span class="stab portability"><code>{feature}</code></span>"#)]

// Can't use cfg_if! because it does not allow nesting :(

// Actually, can't even generate #[cfg]s any other way because of
// https://github.com/rust-lang/rust/pull/52234#issuecomment-486810130

// if #[cfg(feature = "std")] {
#[cfg(feature = "std")]
extern crate std;
#[cfg(feature = "std")]
pub mod prelude {
    pub mod v1 {
        pub use std::prelude::v1::*;
        // Macros aren't included in the prelude for some reason
        pub use std::{dbg, eprint, eprintln, format, print, println, vec};
    }
    pub mod rust_2018 {
        pub use super::v1::*;
        pub use std::prelude::rust_2018::*;
    }
    pub mod rust_2021 {
        pub use super::v1::*;
        pub use std::prelude::rust_2021::*;
    }
}
#[cfg(feature = "std")]
pub use std::*;
// } else {
// The 2 underscores in the crate names are used to avoid
// ambiguity between whether the user wants to use the public
// module std::alloc or the private crate no_std_compat2::alloc
// (see https://gitlab.com/jD91mZM2/no-std-compat/issues/1)

// if #[cfg(feature = "alloc")] {
#[cfg(all(not(feature = "std"), feature = "alloc"))]
extern crate alloc as __alloc;
// }

#[cfg(not(feature = "std"))]
extern crate core as __core;

#[cfg(not(feature = "std"))]
mod generated;

#[cfg(not(feature = "std"))]
pub use self::generated::*;

// if #[cfg(feature = "compat_macros")] {
#[cfg(all(not(feature = "std"), feature = "compat_macros"))]
#[macro_export]
macro_rules! print {
    () => {{}};
    ($($arg:tt)+) => {{
        // Avoid unused arguments complaint. This surely must get
        // optimized away? TODO: Verify that
        let _ = format_args!($($arg)+);
    }};
}
#[cfg(all(not(feature = "std"), feature = "compat_macros"))]
#[macro_export]
macro_rules! println {
    ($($arg:tt)*) => { print!($($arg)*) }
}
#[cfg(all(not(feature = "std"), feature = "compat_macros"))]
#[macro_export]
macro_rules! eprint {
    ($($arg:tt)*) => { print!($($arg)*) }
}
#[cfg(all(not(feature = "std"), feature = "compat_macros"))]
#[macro_export]
macro_rules! eprintln {
    ($($arg:tt)*) => { print!($($arg)*) }
}

#[cfg(all(not(feature = "std"), feature = "compat_macros"))]
#[macro_export]
macro_rules! dbg {
    () => {};
    ($($val:expr),+) => { ($($val),+) }
}
// }
// }
