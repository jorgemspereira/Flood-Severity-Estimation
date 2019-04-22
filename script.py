import datetime
import io
import json
import zipfile

import gdal
import math
import pandas as pd
import requests
import shapefile
from bs4 import BeautifulSoup
from shapely.geometry import Point
from shapely.geometry import shape
from tqdm import tqdm


def make_request(east, north, day, year, table_label):
    url_base = "https://floodmap.modaps.eosdis.nasa.gov"
    url = url_base + "/getTile.php?location={}{}&day={}&year={}".format(east, north, day, year)

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        download_table = soup.find("table", class_="download")
        content_url = url_base + download_table.find("td", text=table_label).next_sibling.next_sibling.a.get("href")
        return requests.get(content_url)
    except (AttributeError, TypeError):
        return None


def get_shapefile(east, north, day, year):
    try:
        dbfname, shpname, shxname = None, None, None
        request = make_request(east, north, day, year, "MODIS Flood Water")
        z = zipfile.ZipFile(io.BytesIO(request.content))
    except (AttributeError, zipfile.BadZipFile):
        return None

    for el in z.namelist():
        if el.endswith(".dbf"):
            dbfname = el
        if el.endswith(".shp"):
            shpname = el
        if el.endswith(".shx"):
            shxname = el

    return shapefile.Reader(shp=io.BytesIO(z.read(shpname)),
                            shx=io.BytesIO(z.read(shxname)),
                            dbf=io.BytesIO(z.read(dbfname)))


def get_geotiff(east, north, day, year):
    try:
        mmap_name = "/vsimem/img"
        request = make_request(east, north, day, year, "MODIS Water Product")
        gdal.FileFromMemBuffer(mmap_name, request.content)
    except AttributeError:
        return None

    gdal_dataset = gdal.Open(mmap_name)
    image = gdal_dataset.GetRasterBand(1)

    cols = gdal_dataset.RasterXSize
    rows = gdal_dataset.RasterYSize

    transform = gdal_dataset.GetGeoTransform()
    x_origin, y_origin = transform[0], transform[3]
    pixel_width, pixel_height = transform[1], -transform[5]

    data = image.ReadAsArray(0, 0, cols, rows)
    gdal.Unlink(mmap_name)

    return x_origin, y_origin, pixel_width, pixel_height, data


def read_dataset_and_metadata(dataset_path, metadata_path):
    all_df = pd.read_csv(dataset_path, names=['filename', 'class'])
    flooded_df = all_df.drop(all_df[all_df['class'] != 1].index).reset_index(drop=True)
    flooded_df = flooded_df.drop(['class'], axis=1).reset_index(drop=True)

    flooded_df['latitude_converted'], flooded_df['longitude_converted'] = None, None
    flooded_df['latitude'], flooded_df['longitude'] = None, None
    flooded_df['year_taken'], flooded_df['day_taken'] = None, None

    with open(metadata_path, encoding="utf-8") as f:
        data = json.load(f, encoding='utf-8')

    return flooded_df, data


def get_flooded_mediaeval_info():
    classification_path = "./datasets/mediaeval2017_devset_gt.csv"
    metadata_path = "./datasets/mediaeval2017_devset_metadata.json"
    flooded_df, metadata = read_dataset_and_metadata(classification_path, metadata_path)

    for index, row in flooded_df.iterrows():
        try:
            image_entry = [obj for obj in metadata['images'] if obj['image_id'] == str(row['filename'])][0]

            date_taken = image_entry['date_taken'].split(".")[0]
            date_taken = datetime.datetime.strptime(date_taken, '%Y-%m-%d %H:%M:%S').timetuple()

            row['year_taken'] = date_taken.tm_year
            row['day_taken'] = date_taken.tm_yday

            row['longitude'] = image_entry['longitude']
            row['latitude'] = image_entry['latitude']

            longitude_converted, latitude_converted = round_coordinates(row['longitude'], row['latitude'])
            row['longitude_converted'] = longitude_converted
            row['latitude_converted'] = latitude_converted

            flooded_df.iloc[index] = row
        except TypeError:
            pass

    return flooded_df.shape[0], flooded_df.dropna().reset_index(drop=True)


def get_flooded_europeanfloods_info():
    classification_path = "./datasets/european_floods_2013_gt.csv"
    metadata_path = "./datasets/european_floods_2013_metadata.json"
    flooded_df, metadata = read_dataset_and_metadata(classification_path, metadata_path)

    for index, row in flooded_df.iterrows():
        try:
            image_entry = [obj for obj in metadata if str(obj['pageid']) == str(row['filename'])][0]

            date_taken = image_entry['capture_time']
            date_taken = datetime.datetime.strptime(date_taken, '%Y-%m-%dT%H:%M:%S').timetuple()

            row['year_taken'] = date_taken.tm_year
            row['day_taken'] = date_taken.tm_yday

            row['longitude'] = image_entry['coordinates']['lon']
            row['latitude'] = image_entry['coordinates']['lat']

            longitude_converted, latitude_converted = round_coordinates(row['longitude'], row['latitude'])
            row['longitude_converted'] = longitude_converted
            row['latitude_converted'] = latitude_converted

            flooded_df.iloc[index] = row
        except (KeyError, IndexError, TypeError):
            pass

    return flooded_df.shape[0], flooded_df.dropna().reset_index(drop=True)


def dd2dms(longitude, latitude):
    split_degx = math.modf(longitude)
    degrees_x = int(split_degx[1])
    minutes_x = abs(int(math.modf(split_degx[0] * 60)[1]))
    seconds_x = abs(round(math.modf(split_degx[0] * 60)[0] * 60, 2))

    split_degy = math.modf(latitude)
    degrees_y = int(split_degy[1])
    minutes_y = abs(int(math.modf(split_degy[0] * 60)[1]))
    seconds_y = abs(round(math.modf(split_degy[0] * 60)[0] * 60, 2))

    eorw = "W" if degrees_x < 0 else "E"
    nors = "S" if degrees_y < 0 else "N"

    x = [abs(degrees_x), minutes_x, seconds_x, eorw]
    y = [abs(degrees_y), minutes_y, seconds_y, nors]

    return x, y


def round_up(x, base=10):
    return x + (base - x) % base


def round_down(x, base=10):
    return x - x % base


def round_coordinates(longitude, latitude):
    longitude_converted, latitude_converted = dd2dms(longitude, latitude)
    longitude_letter, latitude_letter = longitude_converted[-1], latitude_converted[-1]

    longitude_converted = float("{}.{}".format(longitude_converted[0], longitude_converted[1]))
    latitude_converted = float("{}.{}".format(latitude_converted[0], latitude_converted[1]))

    longitude = round_up(longitude_converted) if "W" == longitude_letter else round_down(longitude_converted)
    latitude = round_up(latitude_converted) if "N" == latitude_letter else round_down(latitude_converted)

    longitude = "{}{}".format(str(int(longitude)).zfill(3), longitude_letter)
    latitude = "{}{}".format(str(int(latitude)).zfill(3), latitude_letter)

    return longitude, latitude


def verify_polygons(df):
    found = 0

    for index, row in tqdm(df.iterrows()):
        longitude_converted, latitude_conveted = row['longitude_converted'], row['latitude_converted']
        longitude_init, latitude_init = row['longitude'], row['latitude']

        year, day = row['year_taken'], row['day_taken'] + 1
        shp = get_shapefile(longitude_converted, latitude_conveted, day, year)

        if shp is None:
            continue

        all_shapes = shp.shapes()
        for i in range(len(all_shapes)):
            boundary = all_shapes[i]
            if Point((longitude_init, latitude_init)).within(shape(boundary)):
                found += 1
                print(row)
                break

    return found


def verify_pixels(df):
    found = 0

    for index, row in tqdm(df.iterrows()):
        longitude_converted, latitude_converted = row['longitude_converted'], row['latitude_converted']
        longitude_init, latitude_init = row['longitude'], row['latitude']

        year, day = row['year_taken'], row['day_taken']
        info = get_geotiff(longitude_converted, latitude_converted, day, year)

        if info is None:
            continue

        col_np = int((longitude_init - info[0]) / info[2])
        row_np = int((info[1] - latitude_init) / info[3])
        label = info[-1][row_np][col_np]

        if label == 3:
            print(row)
            found += 1

        else:
            lbs = [info[-1][row_np - 1][col_np - 1], info[-1][row_np - 1][col_np - 0], info[-1][row_np - 1][col_np + 1],
                   info[-1][row_np][col_np - 1], info[-1][row_np][col_np + 1],
                   info[-1][row_np + 1][col_np - 1], info[-1][row_np + 1][col_np - 0], info[-1][row_np + 1][col_np + 1]]

            for label in lbs:
                if label == 3:
                    found += 1
                    print(row)
                    break

    return found


def print_stats(name, total_flooded, total_usable, total_polygons):
    print("------ {:^15s} ------".format(name))
    print("Images Flooded      : {}".format(total_flooded))
    print("Total With Metadata : {}".format(total_usable))
    print("Images with polygon : {}".format(total_polygons))


def main():
    print("Checking MediaEval 2017 dataset.")
    total_images_mediaeval, mediaeval_df = get_flooded_mediaeval_info()
    found_polygons_mediaeval = verify_pixels(mediaeval_df)

    print_stats("MediaEval 2017", total_images_mediaeval,
                mediaeval_df.shape[0], found_polygons_mediaeval)

    print("Checking European Floods dataset.")
    total_images_european_floods, european_floods_df = get_flooded_europeanfloods_info()
    found_polygons_european_floods = verify_pixels(european_floods_df)

    print_stats("European Floods", total_images_european_floods,
                european_floods_df.shape[0], found_polygons_european_floods)


if __name__ == '__main__':
    main()
