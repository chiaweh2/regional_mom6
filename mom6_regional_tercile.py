"""
This script is designed to calculate the tercile value based on the
REGRIDDED forecast/hindcast data. 

"""
# %%
import sys
import warnings
import numpy as np
import xarray as xr
from dask.distributed import Client
import mom6_process as mp

warnings.simplefilter("ignore")

# %%
if __name__=="__main__":

    client = Client(processes=False,memory_limit='150GB',silence_logs=50)
    print(client)
    print(client.cluster.dashboard_link)

    # check argument exist
    if len(sys.argv) < 2:
        print("Usage: python mom6_regional_tercile.py VARNAME")
        sys.exit(1)
    else:
        varname = sys.argv[1]

    # data locations
    MOM6_DIR = "/Datasets.private/regional_mom6/hindcast/"
    MOM6_TERCILE_DIR = "/Datasets.private/regional_mom6/tercile_calculation/"
    file_list = mp.MOM6Misc.mom6_hindcast(MOM6_DIR)
    var_file_list = []
    for file in file_list :
        if varname in file :
            var_file_list.append(file)

    # open data file
    for file in var_file_list :
        ds = xr.open_dataset(file)
        ds_mask = mp.MOM6Static.get_mom6_regionl_mask()

        # apply mask
        da = ds[varname]
        da_area = ds_mask['areacello']
        reg_tercile_list = []
        reg_list = []
        for region in list(ds_mask.keys()):
            if region != 'areacello':
                # calculate the regional area-weighted mean
                da_mask = xr.where(ds_mask[region],1.,np.nan)
                da = (
                    (da*ds_mask[region]*da_area).sum(dim=['xh','yh'])/
                    (ds_mask[region]*da_area).sum(dim=['xh','yh'])
                )   # if regrid of other stagger grid this need to be changed

                # calculate the tercile value
                da_tercile = (
                    da
                    .stack(allens=('init','member'))
                    .quantile(
                        [1./3.,2./3.],
                        dim='allens',
                        keep_attrs=True
                    )
                )
                
                # store all regional averaged tercile
                reg_tercile_list.append(da_tercile)
                reg_list.append(region)
 
        # concat all regional tercile to one DataArray
        da_tercile = xr.concat(reg_tercile_list,dim='region')
        da_tercile['region'] = reg_list

        # store the DataArray to Dataset with tercile seperated 
        ds_tercile = xr.Dataset()
        ds_tercile.attrs = ds.attrs
        ds_tercile['f_lowmid'] = da_tercile.isel(quantile=0)
        ds_tercile['f_midhigh'] = da_tercile.isel(quantile=1)
        ds_tercile = ds_tercile.drop_vars('quantile')

        # output the netcdf file
        print(f'output {MOM6_TERCILE_DIR}{file[len(MOM6_DIR):-3]}.region.nc')
        mp.MOM6Misc.mom6_encoding_attr(
                ds,
                ds_tercile,
                var_names=list(ds_tercile.keys()),
                dataset_name='regional mom6 tercile'
            )
        try:
            ds_tercile.to_netcdf(f'{MOM6_TERCILE_DIR}{file[len(MOM6_DIR):-3]}.region.nc',mode='w')
        except PermissionError:
            print(f'{MOM6_TERCILE_DIR}{file[len(MOM6_DIR):-3]}.region.nc is used by other scripts' )
