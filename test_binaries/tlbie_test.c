/*
 * Author: Nicholas Piggin <npiggin@gmail.com>
 */
#define _GNU_SOURCE
#include <sys/mman.h>
#include <sys/sysinfo.h>
#include <sched.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <signal.h>

static void *mem;
static size_t sz = 1ULL*1024*1024*1024*32;
static size_t lpg_sz = 2*1024*1024;
static size_t pg_sz = 64*1024;
static int nr_procs = 1;

static int set_cpu(int cpu)
{
	cpu_set_t set;

	CPU_ZERO(&set);
	CPU_SET(cpu, &set);

	if (sched_setaffinity(0, sizeof(set), &set) == -1)
		return -1;
	return 0;
}

static void set_random_cpu(void)
{
	while (set_cpu(random() % nr_procs) == -1)
		;
}

static void *mem_walker_fn(void *arg)
{
	for (;;) {
		unsigned long i;

		set_random_cpu();

		for (i = 0; i < sz / lpg_sz; i++) {
			memset(mem + lpg_sz * i, 0, 1);
		}
	}
}

static void *madvise_fn(void *arg)
{
	for (;;) {
		unsigned long i;

		usleep(1000);

		set_random_cpu();

		i = random() % (sz / lpg_sz);
		if (mprotect(mem + lpg_sz * i, lpg_sz, PROT_NONE)) {
			perror("mprotect");
			exit(1);
		}

		usleep(1000);

		if (mprotect(mem + lpg_sz * i, lpg_sz, PROT_READ|PROT_WRITE)) {
			perror("mprotect");
			exit(1);
		}
	}
}

#define NR_THREADS 32

static void SIGSEGV_handler(int signal)
{
	usleep(1000);
}

int main(void)
{
	pthread_t threads[NR_THREADS];
	struct sigaction sa;
	int i;

	nr_procs = get_nprocs_conf();

	memset(&sa, 0, sizeof(struct sigaction));
	sa.sa_handler = SIGSEGV_handler;
	if (sigaction(SIGSEGV, &sa, NULL)) {
		perror("sigaction");
		exit(1);
	}

	posix_memalign(&mem, lpg_sz, sz);

	memset(mem, 0xff, sz);

	if (madvise(mem, sz, MADV_HUGEPAGE)) {
		perror("madvise");
		exit(1);
	}

	for (i = 0; i < NR_THREADS - 1; i++) {
		if (pthread_create(&threads[i], NULL, mem_walker_fn, NULL)) {
			perror("pthread_create");
			exit(1);
		}
	}

	if (pthread_create(&threads[i], NULL, madvise_fn, NULL)) {
		perror("pthread_create");
		exit(1);
	}

	for (i = 0; i < NR_THREADS; i++) {
		if (pthread_join(threads[i], NULL)) {
			perror("pthread_join");
			exit(1);
		}
	}

	exit(0);
}
