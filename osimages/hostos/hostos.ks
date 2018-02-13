#HostOS Preseed for op-test
%pre
%end
url --url={}
text
keyboard --vckeymap=us --xlayouts='us'
services --enabled=NetworkManager,sshd
lang en_US.UTF-8
rootpw {}
skipx
timezone --utc America/New_York
ignoredisk --only-use={}
bootloader  --location=mbr  --append="console=tty0" --timeout=1 --boot-drive={}
zerombr
clearpart --all --initlabel  --drives={}
autopart --type=lvm --fstype=ext4
reboot
%packages --ignoremissing
@core
open-power-host-os-all
%end
%post
%end
