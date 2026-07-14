function [data,head]=read_nasa(file)

% This program reads files that are in NASA Ames 2160 format.
% See, http://badc.nerc.ac.uk

fid=fopen(file);

head.nlhead=fscanf(fid,'%d',1);
head.ffi=fscanf(fid,'%d',1);
fgetl(fid);
head.oname=fgetl(fid);
head.org=fgetl(fid);
head.sname=fgetl(fid);
head.mname=fgetl(fid);
head.ivol=fscanf(fid,'%d',1);
head.nvol=fscanf(fid,'%d',1);
head.date=fscanf(fid,'%d',[1,3]);
head.rdate=fscanf(fid,'%d',[1,3]);

head.dx=fscanf(fid,'%d',1);
head.lenx=fscanf(fid,'%d',1);
fgetl(fid);
head.xname{1}=fgetl(fid);
head.xname{2}=fgetl(fid);
head.nv=fscanf(fid,'%d',1);
head.vscal=fscanf(fid,'%f',[1,head.nv]);
head.vmiss=fscanf(fid,'%f',[1,head.nv]);
fgetl(fid);
head.vname=cell(1,head.nv);
for k=1:head.nv
    head.vname{k}=fgetl(fid);
end

head.nauxv=fscanf(fid,'%d',1);
head.nauxc=fscanf(fid,'%d',1);
head.ascal=cell(1,head.nauxv);
for k=1:(head.nauxv-head.nauxc)
    head.ascal{k}=fscanf(fid,'%f',1);
end
head.amiss=cell(1,head.nauxv);
for k=1:(head.nauxv-head.nauxc)
    head.amiss{k}=fscanf(fid,'%f',1);
end
head.lena=cell(1,head.nauxv);
for k=(head.nauxv-head.nauxc+1):head.nauxv
    head.lena{k}=fscanf(fid,'%d',1);
end
fgetl(fid);
for k=(head.nauxv-head.nauxc+1):head.nauxv
    head.amiss{k}=fgetl(fid);
end
for k=1:head.nauxv
    head.aname{k}=fgetl(fid);
end

head.nscoml=fscanf(fid,'%d',1);
fgetl(fid);
head.scom=cell(1,head.nscoml);
for k=1:head.nscoml
    head.scom{k}=fgetl(fid);
end
head.nncoml=fscanf(fid,'%d',1);
fgetl(fid);
head.ncom=cell(1,head.nncoml);
for k=1:head.nncoml
    head.ncom{k}=fgetl(fid);
end

data.x=cell(1,2);
data.x{2}=fgetl(fid);

head.nx=fscanf(fid,'%d',1);
data.a=cell(1,head.nauxv);
data.a{1}=head.nx;
for k=2:(head.nauxv-head.nauxc)
    data.a{k}=fscanf(fid,'%f',1);
end
fgetl(fid);
for k=(head.nauxv-head.nauxc+1):head.nauxv
    data.a{k}=fgetl(fid);
end

% data.x{1}=zeros(head.nx,1);
% data.v=zeros(head.nx,head.nv);
% for k=1:head.nx
% data.x{1}(k)=fscanf(fid,'%f',1);
% data.v(k,:)=fscanf(fid,'%f',[1,head.nv]);
% end

data.x{1}=[];
data.v=[];
while (feof(fid) == 0)
    ro=fgetl(fid);
    d=sscanf(ro,'%f',[1,inf]);
    if not(all(isspace(ro)))
        data.x{1}=[data.x{1};d(1,1)];
        data.v=[data.v;d(1,2:end)];
    end
end

fclose(fid);

