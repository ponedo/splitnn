package network

import (
	"log"
	"runtime"
	"sync"

	"github.com/vishvananda/netns"
)

type TaskWithArgs func(args ...interface{}) error // Task returns an error

type ThreadPool struct {
	tasks      chan func() // Channel of tasks (closures)
	errors     chan error  // Channel for errors
	wg         sync.WaitGroup
	numWorkers int
	hasError   bool
}

// NewThreadPool initializes the thread pool
func NewThreadPool(numWorkers int) *ThreadPool {
	return &ThreadPool{
		tasks:      make(chan func()),
		errors:     make(chan error), // Buffered channel for error collection
		numWorkers: numWorkers,
		hasError:   false,
	}
}

// Run starts the thread pool workers
func (p *ThreadPool) Run() {
	for i := 0; i < p.numWorkers; i++ {
		go p.worker()
	}
}

// worker executes tasks from the tasks channel
func (p *ThreadPool) worker() {
	// Lock the goroutine to the OS thread
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()

	// Save the original namespace
	originalNS, err := netns.Get()
	if err != nil {
		log.Fatalf("Failed to get the original namespace: %v", err)
	}
	defer originalNS.Close()

	for task := range p.tasks {
		// Run the task with namespace isolation
		taskWrapper := func(task func()) {
			defer func() {
				// Revert to the original namespace after the task
				if err := netns.Set(originalNS); err != nil {
					log.Fatalf("Failed to revert namespace: %v", err)
				}
			}()
			task()
		}

		taskWrapper(task)
		p.wg.Done()
	}
}

// AddTask adds a task with arguments to the thread pool
func (p *ThreadPool) AddTask(task TaskWithArgs, args ...interface{}) {
	p.wg.Add(1)
	p.tasks <- func() {
		err := task(args...)
		if err != nil {
			// Send the error to the errors channel
			p.errors <- err
			p.hasError = true
		}
	}
}

// Wait waits for all tasks to complete and closes the error channel
func (p *ThreadPool) Wait() {
	p.wg.Wait()
}
