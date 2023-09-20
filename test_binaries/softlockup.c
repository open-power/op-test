#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/spinlock.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("LIKHITHA");
MODULE_DESCRIPTION("Kernel Module for softlockups");

static spinlock_t my_lock;

int a;

static int __init my_init(void)
{
    spin_lock_init(&my_lock);
    printk(KERN_INFO "softlockup module: Initialized spinlock\n");

    /* Perform critical section operations */
    spin_lock(&my_lock);
    while (1) {
	a+=1;	
    }
    spin_unlock(&my_lock);

    return 0;
}

static void __exit my_exit(void)
{
    printk(KERN_INFO "Exiting module\n");
}

module_init(my_init);
module_exit(my_exit);
