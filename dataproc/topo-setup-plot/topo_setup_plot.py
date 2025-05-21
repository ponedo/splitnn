import argparse
from itertools import product
from input_data import *
from output_data import *
from plot_utils import *
from thread_pool import *
from collections import OrderedDict

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Process results of a group of tests.")
parser.add_argument("test_results_dir", type=str, help="Path to results of a group of tests.")
parser.add_argument("output_dir", type=str, help="Directory to store results.")
parser.add_argument('--overwrite', dest='overwrite', action='store_true', help="Overwrite existing figures.")
args = parser.parse_args()

###################### Plot options ######################
# Plottable figure types
valid_options = [
    'topo_name', "t", 'b', 'a', 'd', 'N', 'l'
    # 't', 'b', 'a', 'd', 'N', 'l', 'p'
    # 't', 'b', 'a', 'd', 'N', 'l',
]
valid_x_values = [
    'node_num',
    'link_num',
    'b',
    'p'
]
valid_y_values = [
    'node_setup_time',
    'link_setup_time',
    'setup_time',
    'link_clean_time',
    'node_clean_time',
    'clean_time',
]

# Set how to process results
used_options = [
    # 'topo_name', "t", 'b', 'a', 'd', 'N', 'l'
    # "t", 'b', 'a', 'd', 'N', 'l'
    'topo_name', 'b', 'a', 'd', 'N', 'l'
]
curve_options = [
    (),
    # ("t",),
    # ("b",),
    # ("a",),
    # ("p",),
    # ("t", "b"),
    # ("t", "a"),
    # ("b", "a"),
    # ("t", "b", "a"),
]
x_value_types = [
    # 'node_num',
    # 'link_num',
    'b',
    # 'p',
]
y_value_types = [
    'node_setup_time',
    'link_setup_time',
    'setup_time',
    'link_clean_time',
    'node_clean_time',
    'clean_time',
]
filter_values = {
    # "b": 1,
    "topo_name": ["grid_100_100", "clos_32", "as_large"]
}

valid_option_set = set(valid_options)
used_option_set = set(used_options)
if not valid_option_set | used_option_set == valid_option_set:
    print(f"Used options ({used_option_set}) are not within valid options ({valid_option_set})")
    exit(1)

###################### Main ######################

if __name__ == "__main__":
    # Prepare output dir
    if os.path.isfile(args.output_dir):
        print(f"{args.output_dir} already exists as an file!")
        exit(1)
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir, exist_ok=True)

    # # Prepare thread pool
    # pool = ThreadPool(max_workers=5)

    # Read raw results from test_results_dir.
    # Then, store options, topo info, and test result data of all tests in a DataFrame
    print("Reading raw results...")
    all_data_df = get_all_data(
        args.test_results_dir, valid_options, x_value_types, y_value_types, filter_values)
    
    # For each curve option key, a set of figure suites are generated
    # A figure suite corresponds to a set of fixed options
    # A figure suite contains a series of figures
    # Each figure adopts a (x_value_type, y_value_type) pair, and contains a set of curves
    # Each curve corresponds to a set of curve_options value

    for x_value_type, y_value_type in product(x_value_types, y_value_types):
        # For each curve option tuple, how many option-specific figure-suite to draw? Combination of distinct fixed option values!
        for curve_option_keys in curve_options:
            curve_option_keys = sorted(list(
                set(curve_option_keys) - set([x_value_type, y_value_type])
            ))
            print(f"Plotting figure-suite set for curve option keys {curve_option_keys}...")
            # Create a directory for current figure-suite-set
            figure_suite_set_dir = os.path.join(
                args.output_dir, get_figure_suite_set_dirname(curve_option_keys))
            os.makedirs(figure_suite_set_dir, exist_ok=True)
            
            # For each curve option tuple, options that are not curve options are fixed options.
            fixed_option_keys = sorted(list(
                set(used_options) - set(curve_option_keys) - set([x_value_type, y_value_type])
            ))

            # Group by fixed options. Each group corresponds to a "figure-suite"
            groupby_columns = fixed_option_keys if len(fixed_option_keys) > 1 \
                else fixed_option_keys[0]
            suite_groups = all_data_df.groupby(groupby_columns)
            for fixed_option_values, figure_suite_df in suite_groups:
                if len(fixed_option_keys) > 1:
                    fixed_options = dict(zip(fixed_option_keys, fixed_option_values))
                else:
                    fixed_options = {fixed_option_keys[0]: fixed_option_values}
                print(f"Plotting figure-suite for fixed option keys {fixed_options}...")
                
                # Create a directory for current figure-suite
                figure_suite_dir = os.path.join(
                    figure_suite_set_dir, get_figure_suite_dirname(fixed_options))
                os.makedirs(figure_suite_dir, exist_ok=True)

                # Plot one figure in axis (x_value_type, y_value_type)
                print(f"Plotting figure with axes: {x_value_type} {y_value_type}...")
                # pool.add_task(
                #     plot_one_figure, 
                #     figure_suite_df, fixed_options, curve_option_keys,
                #     x_value_type, y_value_type,
                #     figure_suite_dir, args.overwrite)
                plot_one_figure(
                    figure_suite_df, fixed_options, curve_option_keys,
                    x_value_type, y_value_type,
                    figure_suite_dir, args.overwrite
                )

    # pool.wait_for_completion()
    # pool.shutdown()