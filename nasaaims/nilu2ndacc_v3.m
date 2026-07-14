
% Paths (trailing path separator (\) is required).
% Folder for NDACC files must exist. It is not created.
%nilu_path = 'D:\ndacc\nilu\';
%ndacc_path = 'D:\ndacc\ndacc\';


%nilu_path = 'D:\rigel\projects\NDACC\nilu\';
%ndacc_path = 'D:\rigel\projects\NDACC\ndacc\';


nilu_path = 'C:\Rigel\projects\NDACC\nilu\';
ndacc_path = 'C:\Rigel\projects\NDACC\ndacc\';

list = dir(nilu_path);
N_list = length(list);

for k = 1:N_list
    
    if strncmpi(list(k).name, 'so', 2)
        
        disp(list(k).name)
        
        [data, head] = read_nasa([nilu_path, list(k).name]);
        
        start_dn = datenum(head.date) + data.a{2} / 24;
        end_dn = start_dn + data.v(end, 1) / (60 * 60 * 24);
        
        ver = '0001';
        first_line = ...
            ['KIVI R.             O3SONDE     SODANKYLA   OZONE       ', ...
            upper([datestr(start_dn, 'dd-mmm-yyyy HH:MM:SS'), ...
            datestr(end_dn, 'dd-mmm-yyyy HH:MM:SS')]), ver];
 
        fid_nilu = fopen([nilu_path, list(k).name], 'r');
        fid_ndacc = fopen([ndacc_path, list(k).name], 'w');
        
        fprintf(fid_ndacc, '%s\r\n', first_line);

        N_data = data.a{1} - length(find(diff(data.x{1})==0));
        
        kk = 0;
        P2 = 0;
        while ~feof(fid_nilu)
            kk = kk + 1;
            ro = fgetl(fid_nilu);
            try
                P1 = P2;
                P2 = strread(ro, '%f%*f%*f%*f%*f%*f%*f%*f%*f', 1);
                dat = 1;
            catch
                dat = 0;
            end
            if (kk == head.nlhead + 2)
                l_str = length(num2str(data.a{1}));
                ro = strtrim(ro);
                fprintf(fid_ndacc, '%s\r\n', [num2str(N_data, '%4.0f'), ...
                    ro((l_str + 1):end)]);
            elseif (kk > head.nlhead + 2) && (dat == 1) && (P2 == P1)
            else
                fprintf(fid_ndacc, '%s\r\n', ro);
            end
            
        end
        
        fclose(fid_nilu);
        fclose(fid_ndacc);
        
    end
    
end