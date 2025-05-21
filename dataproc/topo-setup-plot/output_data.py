def get_figure_suite_set_dirname(curve_option_keys):
    if curve_option_keys:
        return '--'.join(curve_option_keys)
    else:
        return "mono-curve"


def get_figure_suite_dirname(fixed_options):
    dirname_elements = []
    for fixed_option_key, fixed_option_value in fixed_options.items():
        dirname_elements.append(fixed_option_key)
        dirname_elements.append(str(fixed_option_value))
    return '--'.join(dirname_elements)


def get_figure_filename(x_value_type, y_value_type):
    return f'{x_value_type}--{y_value_type}'
