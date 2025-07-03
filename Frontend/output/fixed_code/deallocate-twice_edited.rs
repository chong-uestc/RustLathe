use std::alloc::{alloc, dealloc, Layout};

fn main() {
    let layout = Layout::from_size_align(1, 1).unwrap(); // Use safe unwrap

    unsafe {
        let x = alloc(layout);
        if x.is_null() {
            panic!("Failed to allocate memory");
        }
        
        // Use the allocated memory for something if necessary

        dealloc(x, layout);
    }
}