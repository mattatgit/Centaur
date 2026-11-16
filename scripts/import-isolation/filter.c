/* Phase 3 ARM64 proof policy. No shell or application tool is registered. */
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <seccomp.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <unistd.h>

int main(int argc, char **argv) {
#ifndef __aarch64__
    return 90;
#endif
    if (argc != 2) return 91;
    scmp_filter_ctx ctx = seccomp_init(SCMP_ACT_ERRNO(EPERM));
    if (!ctx || seccomp_attr_set(ctx, SCMP_FLTATR_ACT_BADARCH, SCMP_ACT_KILL_PROCESS)) return 92;
    /* Default deny, including sockets, mounts, namespace changes, ptrace,
       keyrings, BPF, io_uring, device creation and every unknown syscall. */
    const char *allow[] = {
        "read","write","readv","writev","close","close_range","fstat","newfstatat","statx",
        "lseek","pread64","pwrite64","openat","getdents64","readlinkat","readlink",
        "access","faccessat","faccessat2","getcwd","chdir","fchdir","fcntl","flock",
        "dup","dup2","dup3","pipe","pipe2","poll","ppoll","pselect6","select",
        "epoll_create1","epoll_ctl","epoll_wait","epoll_pwait","epoll_pwait2",
        "mmap","mprotect","munmap","mremap","madvise","brk","msync","mincore",
        "rt_sigaction","rt_sigprocmask","rt_sigreturn","rt_sigtimedwait","rt_sigsuspend",
        "sigaltstack","kill","tkill","tgkill","wait4","waitid","exit","exit_group",
        "execve","getpid","getppid","gettid","getuid","geteuid","getgid","getegid",
        "getresuid","getresgid","getgroups","uname","sysinfo","getrandom",
        "set_tid_address","set_robust_list","get_robust_list","rseq","futex","futex_waitv",
        "clock_gettime","clock_getres","clock_nanosleep","nanosleep","gettimeofday","times",
        "getrusage","getrlimit","prlimit64","sched_getaffinity","sched_yield",
        "getpriority","getpgid","getpgrp","getsid","setsid","setpgid","restart_syscall",
        "mkdir","mkdirat","unlink","unlinkat","rename","renameat","renameat2",
        "ftruncate","truncate","fsync","fdatasync","fchmod","fchmodat","chmod","umask",
        "utimensat","statfs","fstatfs","sendfile","copy_file_range","fadvise64",
        "symlink","symlinkat","link","linkat",NULL
    };
    for (int i=0; allow[i]; ++i) {
        int n=seccomp_syscall_resolve_name(allow[i]);
        if (n>=0 && seccomp_rule_add(ctx,SCMP_ACT_ALLOW,n,0)) return 93;
    }
    /* glibc/Python use FIOCLEX when opening scripts on this ARM64 runtime.
       This only marks a descriptor close-on-exec. All other ioctls, including
       terminal input injection, retain the default denial. */
    if (seccomp_rule_add(ctx,SCMP_ACT_ALLOW,SCMP_SYS(ioctl),1,SCMP_A1(SCMP_CMP_EQ,FIOCLEX))) return 97;
    /* Permit ordinary process/thread creation for the cgroup exhaustion test,
       while refusing every namespace flag. clone3 cannot filter pointed data;
       ENOSYS permits libc's constrained clone fallback. */
    uint64_t ns=CLONE_NEWCGROUP|CLONE_NEWIPC|CLONE_NEWNET|CLONE_NEWNS|CLONE_NEWPID|CLONE_NEWUSER|CLONE_NEWUTS;
    if (seccomp_rule_add(ctx,SCMP_ACT_ALLOW,SCMP_SYS(clone),1,SCMP_A0(SCMP_CMP_MASKED_EQ,ns,0))) return 94;
    if (seccomp_rule_add(ctx,SCMP_ACT_ERRNO(ENOSYS),SCMP_SYS(clone3),0)) return 95;
    int fd=open(argv[1],O_WRONLY|O_CREAT|O_EXCL,0400);
    if (fd<0 || seccomp_export_bpf(ctx,fd)) return 96;
    close(fd);seccomp_release(ctx);return 0;
}
