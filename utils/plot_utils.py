import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd


def draw_plot(result):
    final_result = []
    first, second = [], []
    for index, row in result.iterrows():

        if row['class'] == 1:
            height = row['eight_neighbors_avg'] - row['eight_neighbors_min']
            first.append(height)
            height = min(1.0, height)

        elif row['class'] == 2:
            height = row['twenty_four_neighbors_max'] - row['twenty_four_neighbors_avg']
            height = height if height > 1 else row['forty_eight_neighbors_max'] - row['forty_eight_neighbors_avg']
            height = height if height > 1 else row['eighty_neighbors_max'] - row['eighty_neighbors_avg']
            height = height if height > 1 else row['one_hundred_twenty_neighbors_max'] - row['one_hundred_twenty_neighbors_avg']
            height = height if height > 1 else row['one_hundred_sixty_eight_neighbors_max'] - row['one_hundred_sixty_eight_neighbors_avg']
            second.append(height)
            height = max(1.0, height)

        else:
            raise ValueError("Class should be equal to 1 or 2.")

        final_result.append((row['filename'], row['font'], row['class'], height))

    print("Class LESS than 1 meter.")
    print("Number of zeros   : {:05.2f} %".format(100 * sum(x == 0 for x in first) / len(first)))
    print("Above 1 meter     : {:05.2f} %".format(100 * sum(x > 1.0 for x in first) / len(first)))

    print("Class MORE than 1 meter.")
    print("Above 3 meters    : {:05.2f} %".format(100 * sum(x > 3.0 for x in second) / len(second)))
    print("Above 5 meters    : {:05.2f} %".format(100 * sum(x > 5.0 for x in second) / len(second)))
    print("Less than 1 meter : {:05.2f} %".format(100 * sum(x < 1.0 and x != 0 for x in second) / len(second)))
    print("Number of zeros   : {:05.2f} %".format(100 * sum(x == 0 for x in second) / len(second)))

    fig, ax = plt.subplots()
    bp1 = ax.boxplot([t[3] for t in final_result if t[2] == 1], positions=[1], patch_artist=True, widths=[0.8])
    bp2 = ax.boxplot([t[3] for t in final_result if t[2] == 2], positions=[2], patch_artist=True, widths=[0.8])
    bp3 = ax.boxplot([t[3] for t in final_result if t[2] == 1 or t[2] == 2], positions=[3], patch_artist=True, widths=[0.8])

    bp1['boxes'][0].set_facecolor("lightblue")
    bp2['boxes'][0].set_facecolor("lightgreen")
    bp3['boxes'][0].set_facecolor("lightpink")

    ax.set_yscale("symlog", basey=2)
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:.0f}'))
    ax.yaxis.set_minor_formatter(mticker.NullFormatter())
    ax.set_ylim(-0.1, 10)
    ax.set_xlim(0, 4)
    plt.yticks([0, 1, 2, 4, 8], [0, 1, 2, 4, 8])
    plt.xticks([1, 2, 3], ["Less 1 Meter\n", "More 1 Meter\n", "Overall\n"])
    plt.hlines([1, 2, 4, 8], xmin=0, xmax=10, linestyles="dotted", linewidth=0.5)
    plt.title('Estimated Water Depth')

    fig.tight_layout()
    plt.savefig('heights.png')

    df = pd.DataFrame(final_result, columns=['filename', 'font', 'class', 'height'])
    df.to_csv("result.csv", index=False)
