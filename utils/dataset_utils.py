import datetime
import json

import math
import pandas as pd


def read_dataset_and_metadata(dataset_path, metadata_path, drop_no_flood):
    flooded_df = pd.read_csv(dataset_path, names=['filename', 'class'])

    if drop_no_flood:
        flooded_df = flooded_df.drop(flooded_df[flooded_df['class'] != 1].index).reset_index(drop=True)

    flooded_df['year'], flooded_df['month'], flooded_df['day'] = None, None, None
    flooded_df['latitude_converted'], flooded_df['longitude_converted'] = None, None
    flooded_df['latitude'], flooded_df['longitude'] = None, None

    with open(metadata_path, encoding="utf-8") as f:
        data = json.load(f, encoding='utf-8')

    return flooded_df, data


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


def round_coordinates(longitude, latitude):
    longitude_converted, latitude_converted = dd2dms(longitude, latitude)
    longitude_letter, latitude_letter = longitude_converted[-1], latitude_converted[-1]

    longitude = longitude_converted[0]
    latitude = latitude_converted[0]

    longitude = longitude + 1 if "W" == longitude_letter else longitude
    latitude = latitude if "N" == latitude_letter else latitude + 1

    longitude = "{}{}".format(longitude_letter, str(int(longitude)).zfill(3))
    latitude = "{}{}".format(latitude_letter, str(int(latitude)).zfill(3))

    return longitude, latitude


def get_flooded_mediaeval_info(classification_path, metadata_path, drop_no_flood=True):
    flooded_df, metadata = read_dataset_and_metadata(classification_path, metadata_path, drop_no_flood)

    for index, row in flooded_df.iterrows():
        try:
            image_entry = [obj for obj in metadata['images'] if obj['image_id'] == str(row['filename'])][0]

            date_taken = image_entry['date_taken'].split(".")[0]
            date_taken = datetime.datetime.strptime(date_taken, '%Y-%m-%d %H:%M:%S').timetuple()

            row['year'] = date_taken.tm_year
            row['month'] = date_taken.tm_mon
            row['day'] = date_taken.tm_mday

            row['longitude'] = image_entry['longitude']
            row['latitude'] = image_entry['latitude']

            longitude_converted, latitude_converted = round_coordinates(row['longitude'], row['latitude'])
            row['longitude_converted'] = longitude_converted
            row['latitude_converted'] = latitude_converted

            flooded_df.iloc[index] = row
        except TypeError:
            pass

    return flooded_df.dropna().reset_index(drop=True)


def get_flooded_europeanfloods_info(drop_no_flood=True):
    classification_path = "./datasets/european_floods_2013_gt.csv"
    metadata_path = "./datasets/european_floods_2013_metadata.json"
    flooded_df, metadata = read_dataset_and_metadata(classification_path, metadata_path, drop_no_flood)

    for index, row in flooded_df.iterrows():
        try:
            image_entry = [obj for obj in metadata if str(obj['pageid']) == str(row['filename'])][0]

            date_taken = image_entry['capture_time']
            date_taken = datetime.datetime.strptime(date_taken, '%Y-%m-%dT%H:%M:%S').timetuple()

            row['year'] = date_taken.tm_year
            row['month'] = date_taken.tm_mon
            row['day'] = date_taken.tm_mday

            row['longitude'] = image_entry['coordinates']['lon']
            row['latitude'] = image_entry['coordinates']['lat']

            longitude_converted, latitude_converted = round_coordinates(row['longitude'], row['latitude'])
            row['longitude_converted'] = longitude_converted
            row['latitude_converted'] = latitude_converted

            flooded_df.iloc[index] = row
        except (KeyError, IndexError, TypeError):
            pass

    return flooded_df.dropna().reset_index(drop=True)


def replace_class(result_df):
    values_mediaeval_test_df = pd.read_csv("./datasets/mediaeval2017_testset_severity.csv", names=['filename', 'class'])
    values_mediaeval_train_df = pd.read_csv("./datasets/mediaeval2017_devset_severity.csv", names=['filename', 'class'])
    values_european_floods_df = pd.read_csv("./datasets/european_floods_2013_severity.csv", names=['filename', 'class'])

    values_final = values_mediaeval_test_df.append(values_mediaeval_train_df, ignore_index=True)
    values_final = values_final.append(values_european_floods_df, ignore_index=True)
    values_final = values_final.astype(str).set_index('filename')

    for index, row in result_df.iterrows():
        row['class'] = values_final.loc[str(int(row['filename'])), :]['class']
        result_df.iloc[index] = row

    result_df['filename'] = result_df['filename'].astype(int).astype(str)
    result_df['class'] = result_df['class'].astype(int)

    result_df = result_df.replace({'class': {3: 2}})
    result_df = result_df.drop(result_df[result_df['class'] == 4].index).reset_index(drop=True)

    return result_df
