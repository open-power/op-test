# RHEL Preseed for op-test
%pre
%end
url --url={} --proxy={}
text
keyboard --vckeymap=us --xlayouts='us'
lang en_US.UTF-8
rootpw --plaintext {}
skipx
timezone --utc America/New_York
clearpart --all --initlabel --drives={}
bootloader  --location=mbr  --boot-drive={}
ignoredisk --only-use={}
autopart --type=lvm --fstype=ext4
services --enabled=NetworkManager,sshd
reboot
%packages --ignoremissing
@core
kexec-tools
telnet
java
kernel-devel
kernel-headers
gcc
make
gcc-c++
numactl
openssh-server
wget
net-tools
libX11-devel
mesa-libGLU-devel
freeglut-devel
ntpdate
lm_sensors
ipmitool
i2c-tools
pciutils
kernel-tools
nano
sysstat
rpm-build
gcc-gfortran
hdparm
tk
tcsh
lsof
python-devel
%end
