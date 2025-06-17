use std::alloc::{alloc, dealloc, Layout};

// A structure to safely manage allocated memory
struct AllocatedMemory {
    ptr: *mut u8,
    layout: Layout,
}

impl AllocatedMemory {
    // Allocates memory and returns an instance of AllocatedMemory
    fn new(size: usize, align: usize) -> Self {
        let layout = Layout::from_size_align(size, align).unwrap();
        let ptr = unsafe { alloc(layout) };
        AllocatedMemory { ptr, layout }
    }

    // Deallocate the memory safely
    fn deallocate(self) {
        unsafe {
            dealloc(self.ptr, self.layout);
        }
    }
}

fn main() {
    let memory = AllocatedMemory::new(1, 1);
    // Use the allocated memory here if needed
    // Memory will be automatically freed when it goes out of scope
    // Deallocate the memory safely
    memory.deallocate();
}