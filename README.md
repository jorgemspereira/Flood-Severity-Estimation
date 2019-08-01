# Flood Severity Estimation Algorithm

This repository contains the implementation for a "Flood Severity Estimation Algorithm", that tries to estimate the 
height of the water in geo-referenced photos that depict floods. This algorithm uses the Digital Elevation 
Model (DEM) from the Japan Aerospace eXploration Agency (JAXA). 

To fill the "NO DATA VALUES" from the JAXA's DEM, the DEMs from the Shuttle Radar Topography Mission (SRTM)
and the EU-DEM are used. The file for the SRTM DEM can be obtained 
[here](https://drive.google.com/open?id=1pHF-fClkc27zk0lNJX4i1LOyywkQM07a) and the files 
for the EU-DEM [here](https://land.copernicus.eu/imagery-in-situ/eu-dem/eu-dem-v1.1?tab=download). 

These files needed to be placed ain the folder as described below.

```
project
│   datasets
│   results
└─── dems
│   │   srtm30_merged.tif
│   │   eu_dem.tif
│   flood_severity_estimation.py
│   README.md
```

### Execution

This implementation was developed using Python 3.6.7 and relies heavily on [GDAL](https://pypi.org/project/GDAL/) library. To run the algorithm over the information in the **dataset** folder simple execute the script:

```console
$ python3 flood_severity_estimation.py
```