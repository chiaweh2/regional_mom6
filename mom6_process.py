#!/usr/bin/env python

"""
This is the script to genearte the tercile plot based on the 
forecast(hindcast) that is generated by Andrew Ross at GFDL.

"""
from typing import (
    Literal,
    List
)
from datetime import date
from dateutil.relativedelta import relativedelta
import cftime
import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import norm as normal
import warnings

warnings.simplefilter("ignore")
xr.set_options(keep_attrs=True)

class mom6_forecast:
    """
    Class for various mom6 forecast related calculation
    1. getting the mom6 files
    2. calculate the forecast probability in each tercile
    ...
    """
    def __init__(
        self,
        iyear : int,
        imonth : int,
        var : str,
        source : Literal['raw','regrid'] = 'regrid'
    ) -> None:
        """
        mom6_tercile class needed attribute value

        Parameters
        ----------
        imonth : int
            initial year of forecast
        imonth : int
            initial month
        var : str
            variable name one want to exetract from the data
        source : Literal[&#39;raw&#39;,&#39;regrid&#39;], optional
            The data extracted should be the regridded result or 
            the original model grid (curvilinear), by default 'raw'

        """
        self.var = var
        self.iyear = iyear
        self.imonth = imonth
        self.source = source
        
    def mom6_hindcast(
        self,
        hindcast_dir : str
    ) -> List[str]:
        """
        Create list of files to be able to be opened 
        by Xarray.

        Parameters
        ----------
        hindcast_dir : str
            directory path in string to the forecast/hindcast

        Returns
        -------
        List 
            A list of all data name including directory path 
            for the hindcast/forecast data
           
        """
        # input of array of different variable forecast
        tob_files = [f"tob_forecasts_i{mon}.nc" for mon in range(3,13,3)]
        tos_files = [f"tos_forecasts_i{mon}.nc" for mon in range(3,13,3)]

        # h point list
        hpoint_file_list = (
            tob_files+
            tos_files
        )

        hpoint_file_list = [f"{hindcast_dir}{file}" for file in hpoint_file_list]

        all_file_list = hpoint_file_list

        return all_file_list

    def get_mom6(self) -> xr.Dataset:
        """
        Return the mom6 rawgrid/regridded hindcast/forecast field
        with the static field combined and setting the
        lon lat related variables to coordinate 

        Returns
        -------
        xr.Dataset
            The Xarray Dataset object is the merged dataset of
            all forecast field include in the `file_list`. The
            Dataset object is lazily-loaded.
        """
        if self.source == 'raw' :
            # getting the forecast/hindcast data
            mom6_dir = "/Datasets.private/regional_mom6/hindcast/"
            file_list = self.mom6_hindcast(mom6_dir)

            # static field
            ds_static = xr.open_dataset('/Datasets.private/regional_mom6/ocean_static.nc')
            ds_static = ds_static.set_coords(
                ['geolon','geolat',
                'geolon_c','geolat_c',
                'geolon_u','geolat_u',
                'geolon_v','geolat_v']
            )

            # merge the static field with the variables
            for file in file_list:
                iyear_flag = f'i{self.iyear}' in file
                imon_flag = f'i{self.imonth}' in file
                var_flag = self.var in file
                if imon_flag and var_flag :
                    ds = xr.open_dataset(file).sel(init=f'{self.iyear}-{self.imonth}')

            ds = xr.merge([ds_static,ds])

        elif self.source == 'regrid':
            # getting the forecast/hindcast data
            mom6_dir = "/Datasets.private/regional_mom6/hindcast/regrid/"
            file_list = self.mom6_hindcast(mom6_dir)

            # read only the needed file
            for file in file_list:
                iyear_flag = f'i{self.iyear}' in file
                imon_flag = f'i{self.imonth}' in file
                var_flag = self.var in file
                if imon_flag and var_flag :
                    ds = xr.open_dataset(file).sel(init=f'{self.iyear}-{self.imonth}')

        return ds

    def get_mom6_tercile(self) -> xr.Dataset:
        """return the mom6 quantile from the forecast

        Returns
        -------
        xr.Dataset
            A dataset that include the f_lowmid and f_midhigh value which 
            represent SST values at the boundaries between the terciles. 
            `f_lowmid` represent the boundary value between lower and middle
            tercile. `f_midhigh` represent the boundary value between middle
            and upper tercile. (the filename 'quantile' MIGHT be error naming)
        """
        if self.source == 'raw':
            # getting the forecast/hindcast tercile data
            mom6_dir = "/Datasets.private/regional_mom6/tercile_calculation/"
            return xr.open_dataset(f'{mom6_dir}/forecast_quantiles_i{self.imonth:02d}.nc')

        elif self.source == 'regrid':
            # getting the regridd forecast/hindcast tercile data
            mom6_dir = "/Datasets.private/regional_mom6/tercile_calculation/regrid/"
            return xr.open_dataset(f'{mom6_dir}/{self.var}_forecasts_i{self.imonth}.nc')


    def get_init_fcst_time(
        self,
        lead_bins : List[int] = [0, 3, 6, 9, 12]
    ) -> dict:
        """_summary_

        Parameters
        ----------
        lead_bins : List[int]
            The `lead_bin` used to binned the leading month result
            example is `lead_bins = [0, 3, 6, 9, 12]` for four seasonal
            mean.

        Returns
        -------
        dict
            with two key-value pairs, 'init': initial_time and
            'fcst': mean forecasted during the binned period 
        """
        # get the cftime of initial time
        btime = cftime.datetime(self.iyear,self.imonth,1)

        # store the forecast time format based on all leadtime
        forecasttime = []
        period_length = lead_bins[1]-lead_bins[0]-1  # assuming the bins are equal space
        for l in range(0,12):
            # leadtime period start
            sdate = (
                date.fromisoformat(f'{btime.year}-'+
                                    f'{btime.month:02d}-'+
                                    f'{1:02d}')
                +relativedelta(months=l)
            )
            # leadtime period end
            fdate = (
                date.fromisoformat(f'{btime.year}-'+
                                    f'{btime.month:02d}-'+
                                    f'{1:02d}')
                +relativedelta(months=l+period_length)
            )
            # store array of forecast 3 month period
            forecasttime.append(f'{sdate.strftime("%b")}-{fdate.strftime("%b %Y")}')

        # construct forecast period only during the binned period
        mean_forecasttime = [forecasttime[idx] for idx in lead_bins[:-1]]

        # get the initial time
        ini_time_date = (
            date.fromisoformat(
                f'{btime.year}-'+
                f'{btime.month:02d}-'+
                f'{1:02d}'
            )
        )
        # construct the initial time format
        ini_time = f'{ini_time_date.strftime("%b %Y")}'

        return {'init':ini_time,'fcsts':mean_forecasttime}
    
    def calculate_tercile_prob(
        self,
        lead_bins : List[int] = None
    ) -> xr.Dataset:
        """
        use single initialization's normal distribution
        and pre-defined tercile value based on the long-term 
        statistic tercile value to find the probability of
        upper ,normal , and lower tercile
        
        It also find the largest probability in upper (positive),
        normal (0), lower (negative)

        Parameters
        ----------
        lead_bins : List[int]
            The `lead_bin` used to binned the leading month result
            default is `lead_bins = [0, 3, 6, 9, 12]` for four seasonal
            mean.
        
        Returns
        -------
        xr.Dataset
            two variables are in the dataset. (1) tercile_prob 
            (2) tercile_prob_max. 

            1 is a 4D matrix with the dimension 
            of lon x lat x lead x 3. This are the probability of
            upper(lon x lat x lead), normal(lon x lat x lead),
            and lower tercile(lon x lat x lead)

            2 is the 3D matrix of largest probability in upper (positive),
            normal (0), lower (negative) with dimension of (lon x lat x lead)
        """

        # loaded the mom6 raw field
        ds_data = self.get_mom6()

        # load variable to memory
        da_data = ds_data[self.var].isel(init=0)

        if lead_bins is None:
            # average the forecast over the lead bins
            da_binned = da_data.rename({'lead': 'lead_bin'})
        else:
            # setup lead bins to average during forecast lead time
            # (should match lead bins used for the historical data
            # that created the /Datasets.private/regional_mom6/tercile_calculation/historical_terciles.nc
            # [0, 3, 6, 9, 12] produces 3-month averages
            lead_bin_label = np.arange(0,len(lead_bins)-1)

            # average the forecast over the lead bins
            da_binned = (
                da_data
                .groupby_bins('lead', lead_bins, labels=lead_bin_label, right=True)
                .mean('lead')
                .rename({'lead_bins': 'lead_bin'})
            )

        # find a normal distribution for each grid cell and lead bin
        # from the ensemble mean and standard deviation
        #  this is based on 1 initialization
        da_mean = da_binned.mean('member')
        da_std = da_binned.std('member')
        da_dist = normal(loc=da_mean, scale=da_std)

        # load the predetermined hindcast/forecast tercile value
        #  this is based on 30 years statistic 1993-2023
        ds_tercile = self.get_mom6_tercile()

        if lead_bins is None:
            ds_tercile_binned = ds_tercile.rename({'lead': 'lead_bin'})
        else:
            # average the forecast over the lead bins
            ds_tercile_binned = (
                ds_tercile
                .groupby_bins('lead', lead_bins, labels=lead_bin_label, right=True)
                .mean('lead')
                .rename({'lead_bins': 'lead_bin'})
            )

        # use single initialization's normal distribution
        # and pre-defined tercile value to find the
        # probability based on the single initialization
        # that correspond to the long-term statistic tercile value

        #---probability of lower tercile tail
        da_low_tercile_prob = xr.DataArray(
            da_dist.cdf(ds_tercile_binned['f_lowmid']),
            dims=da_mean.dims,
            coords=da_mean.coords
        )
        #---probability of upper tercile tail
        da_up_tercile_prob = 1 - xr.DataArray(
            da_dist.cdf(ds_tercile_binned['f_midhigh']),
            dims=da_mean.dims,
            coords=da_mean.coords
        )
        #---probability of between lower and upper tercile
        da_mid_tercile_prob = 1 - da_up_tercile_prob - da_low_tercile_prob

        da_tercile_prob = xr.concat(
            [da_low_tercile_prob,da_mid_tercile_prob,da_up_tercile_prob],
            pd.Index([-1,0,1],name="tercile")
        )

        # lower tercile max => negative
        # nomral tercile max => 0
        # upper tercile max => positive
        da_tercile_prob_max = (
            da_tercile_prob.idxmax(dim='tercile',fill_value=np.nan)*
            da_tercile_prob.max(dim='tercile')
        )

        # create dataset to store the tercile calculation
        ds_tercile_prob=xr.Dataset()
        ds_tercile_prob['tercile_prob'] = da_tercile_prob
        ds_tercile_prob['tercile_prob_max'] = da_tercile_prob_max

        return ds_tercile_prob