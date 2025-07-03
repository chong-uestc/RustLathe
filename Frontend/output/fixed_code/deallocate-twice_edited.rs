use std::alloc::{alloc, dealloc, Layout};

//@error-in-other-file: has been freed

fn main() {
    unsafe {
        let layout = Layout::from_size_align_unchecked(1, 1);
        let x = alloc(layout);
        
        // Assert that x is valid before deallocating
        assert!(!x.is_null(), "Pointer x should not be null before dealloc.");

        dealloc(x, layout);
        
        // x is no longer valid after deallocating; we should not use it again
    }
}