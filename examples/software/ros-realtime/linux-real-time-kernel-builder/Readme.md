Contributed by: Istemi Ekin Akkus

Integrated and tested by: Istemi Ekin Akkus

This folder contains the computation code for building the `RT_PREEMPT kernel for Raspberry Pi` from the ROS 2 Real-Time Working Group, slightly modified from the [original repo](https://github.com/ros-realtime/linux-real-time-kernel-builder).

The build arguments for the container image are fixed to the following:
```bash
ARG UNAME_R=6.8.0-1005-raspi
ARG RT_PATCH=patch-6.8.2-rt11
```
Afterwards, the necessary commands to build the `.deb` packages are issued as well as a simple script to copy them to the output.

The full diff of the `Dockerfile`s is as follows:

```bash
51,52c51,52
< ARG UNAME_R=6.8.0-1005-raspi
< ARG RT_PATCH=6.8.2-rt11
---
> ARG UNAME_R
> ARG RT_PATCH
108c108
< # VOLUME /linux_build
---
> VOLUME /linux_build
179,189d178
<
< RUN cd /linux_build/${KERNEL_DIR} \
<     && make ARCH=${ARCH} CROSS_COMPILE=${triple}- LOCALVERSION=-raspi -j `nproc` bindeb-pkg
<
< RUN mkdir -p /tmp/inputs/
< RUN mkdir -p /tmp/outputs/
<
< ADD copy_files.sh /tmp/
< RUN sudo chmod +x /tmp/copy_files.sh
<
< CMD ["/tmp/./copy_files.sh"]
```

Note that the `VOLUME /linux_build` statement has been commented out due to the following reason: https://stackoverflow.com/questions/27641091/docker-git-clone-during-build-is-not-cloning-and-not-erroring.

Note also that URLs using `http://` have been updated to `https://` (i.e., https://ports.ubuntu.com and https://cdn.kernel.org).
