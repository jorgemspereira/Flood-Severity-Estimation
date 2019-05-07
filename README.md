# Flood Severity Estimation Algorithm

This repository contains the implementation for a "Flood Severity Estimation Algorithm", that tries to estimate the height of the water in geo-referenced photos that depict floods. This algorithm uses the satellite images described by Groeve (2010) and the Digital Elevation Model (DEM) from the Japan Aerospace eXploration Agency (JAXA).

    @article{groeve2010floods,
        author  = {Tom De Groeve},
        title   = {Flood monitoring and mapping using passive microwave remote sensing in Namibia},
        journal = {Geomatics, Natural Hazards and Risk},
        volume  = {1},
        number  = {1},
        year    = {2010}
    }

To fill the "NO DATA VALUES" from the JAXA's DEM, the DEM from the Shuttle Radar Topography Mission (SRTM) is used (after interpolated to the same resolution of JAXA). The file can be obtained [here](https://drive.google.com/open?id=1pHF-fClkc27zk0lNJX4i1LOyywkQM07a) and needs to be placed in the folder as described below.

```
project
│   datasets
│   results
└─── srtm30_merged
│   │   srtm30_merged.tif
│   flood_severity_estimation.py
│   README.md
```

### Execution

This implementation was developed using Python 3.6.7 and relies heavily on [GDAL](https://pypi.org/project/GDAL/) library. To run the algorithm over the information in the **dataset** folder simple execute the script:

```console
$ python3 flood_severity_estimation.py
```