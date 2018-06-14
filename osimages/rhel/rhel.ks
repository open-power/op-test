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
%packages
@core
kexec-tools
telnet
java
%end
