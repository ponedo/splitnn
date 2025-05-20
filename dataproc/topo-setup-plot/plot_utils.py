import os
import matplotlib.pyplot as plt
from output_data import *

def get_figure_title(fixed_options):
    dirname_elements = []
    for fixed_option_key, fixed_option_value in fixed_options.items():
        dirname_elements.append(fixed_option_key)
        dirname_elements.append(str(fixed_option_value))
    return '--'.join(dirname_elements)


def plot_one_curve(
    curve_df, curve_options,
    x_value_type, y_value_type,
    output_dir, output_filename_prefix):
    plt.plot(
        curve_df[x_value_type],
        curve_df[y_value_type],
        marker='o',
        label=f'{curve_options}' if curve_options else None
    )
    curve_df.to_csv(
        os.path.join(output_dir, output_filename_prefix + ".csv"),
        index=False, header=True)


def plot_one_figure(
        figure_df, fixed_options, curve_option_keys,
        x_value_type, y_value_type,
        output_dir, overwrite):
    # Check whether need plotting
    output_filename_prefix = get_figure_filename(
        x_value_type, y_value_type)
    output_filepath = os.path.join(
        output_dir, output_filename_prefix + ".png")
    if os.path.exists(output_filepath) and not overwrite:
        print(f"Figure already exists: {output_filepath}")
        return

    # Sort the dataframe first
    figure_df = figure_df.sort_values(by=['t', x_value_type])

    # Create a figure and axis
    plt.figure(figsize=(10, 6))

    # Iterate through unique curves
    if len(curve_option_keys) == 0:
        curve_options = {}
        curve_df = figure_df
        plot_one_curve(
            curve_df, None,
            x_value_type, y_value_type,
            output_dir, output_filename_prefix)
    else:
        groupby_columns = list(curve_option_keys) if len(curve_option_keys) > 1 \
            else curve_option_keys[0]
        for curve_option_values, curve_df in figure_df.groupby(groupby_columns):
            # sorted_curve_df = curve_df.sort_values(by=x_value_type)
            if len(curve_option_keys) > 1:
                curve_options = dict(zip(curve_option_keys, curve_option_values))
            else:
                curve_options = {curve_option_keys[0], curve_option_values}
            plot_one_curve(
                curve_df, curve_options,
                x_value_type, y_value_type,
                output_dir, output_filename_prefix)

    # Label different topology
    if 't' not in curve_option_keys and x_value_type in ['node_num', 'link_num']:
        for topo_type, topo_df in figure_df.groupby('t'):
            for x_value in topo_df[x_value_type].unique():
                sub_df = topo_df[topo_df[x_value_type] == x_value]
                max_y_row = sub_df[sub_df[x_value_type] == sub_df[x_value_type].max()].iloc[0]
                plt.axvline(x=x_value, linestyle='--', color='gray', alpha=0.5)
                plt.text(
                    x_value, max_y_row[y_value_type],
                    str(max_y_row['topo_name']),
                    verticalalignment='bottom',
                    horizontalalignment='center')

    # for _, row in figure_df.iterrows():
    #     if row[x_scale] not in labeled_x_values:
    #         plt.axvline(x=row[x_scale], linestyle='--', color='gray', alpha=0.5)
    #         plt.text(row[x_scale], row[y_value], str(row['topo_name']), verticalalignment='bottom', horizontalalignment='center')
    #         labeled_x_values.add(row[x_scale])

    # Adding labels and title
    title = get_figure_title(fixed_options)
    plt.xlabel(x_value_type)
    plt.ylabel(y_value_type)
    plt.title(title)
    if curve_options:
        plt.legend()
    plt.grid()

    # Save figure
    plt.savefig(output_filepath, bbox_inches='tight')
    print(output_filepath)
    plt.close()
