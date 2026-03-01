try:
    from .revit_helpers import (
        get_active_document, get_revit_version, get_revit_year, is_revit_available,
        get_all_levels, get_level_by_name, get_all_grids, get_all_columns,
        get_all_beams, get_all_walls, get_all_floors, get_all_doors,
        get_all_windows, get_all_foundations, get_all_structural_framing,
        get_all_structural_columns, get_elements_by_level, get_columns_by_level,
        get_beams_by_level, get_walls_by_level, get_parameter_value,
        set_parameter_value, has_parameter, mm_to_feet, feet_to_mm,
        m_to_feet, feet_to_m, cm_to_feet, feet_to_cm,
        get_element_location_point, get_element_location_curve, get_element_location,
        get_bounding_box, get_bounding_box_center, get_bounding_box_dimensions,
        with_transaction, get_selected_elements, get_document_info,
        get_project_info, get_username
    )
    REVIT_HELPERS_AVAILABLE = True
except ImportError as e:
    REVIT_HELPERS_AVAILABLE = False
    print("Warning: revit_helpers non disponible - " + str(e))

try:
    from .geometry_helpers import (
        mm_to_feet as geo_mm_to_feet, feet_to_mm as geo_feet_to_mm,
        m_to_feet as geo_m_to_feet, feet_to_m as geo_feet_to_m,
        distance_between_points, distance_between_points_mm, midpoint, centroid,
        is_point_on_line, project_point_on_line, offset_point,
        vector_from_points, normalize_vector, vector_length,
        dot_product, cross_product, angle_between_vectors,
        create_line, get_curve_length, get_curve_midpoint, get_curve_endpoints,
        intersect_lines, intersect_line_and_plane,
        create_rectangle_loop, create_circle_loop, points_to_curve_loop, is_rectangle,
        point_to_dict, point_to_dict_mm, dict_to_point, points_to_list,
        is_valid_point, is_valid_curve
    )
    GEOMETRY_HELPERS_AVAILABLE = True
except ImportError as e:
    GEOMETRY_HELPERS_AVAILABLE = False
    print("Warning: geometry_helpers non disponible - " + str(e))

try:
    from .conversion_helpers import (
        mm_to_cm, cm_to_mm, m_to_mm, mm_to_m, m_to_cm, cm_to_m,
        kn_to_n, n_to_kn, kn_to_lbs, lbs_to_kn,
        mpa_to_kpa, kpa_to_mpa, mpa_to_psi, psi_to_mpa, mpa_to_kgf_cm2, kgf_cm2_to_mpa,
        m2_to_cm2, cm2_to_m2, m2_to_mm2, mm2_to_m2,
        m3_to_l, l_to_m3, m3_to_cm3, cm3_to_m3,
        kg_to_t, t_to_kg, kg_to_lbs, lbs_to_kg,
        celsius_to_fahrenheit, fahrenheit_to_celsius, deg_to_rad, rad_to_deg,
        format_mm_to_m, format_mm_to_cm, format_area_m2,
        format_volume_m3, format_load_kN, format_pressure_MPa
    )
    CONVERSION_HELPERS_AVAILABLE = True
except ImportError as e:
    CONVERSION_HELPERS_AVAILABLE = False
    print("Warning: conversion_helpers non disponible - " + str(e))

try:
    from .ui_helpers import (
        show_message_box, show_task_dialog, show_error_dialog,
        show_warning_dialog, show_info_dialog, show_question_dialog,
        alert, confirm, prompt_for_string, prompt_for_integer, prompt_for_float,
        select_from_list, select_from_dict, ProgressBar, with_progress,
        WPFWindow, create_wpf_window, show_toast, show_balloon_tip,
        open_url, copy_to_clipboard, show_in_explorer
    )
    UI_HELPERS_AVAILABLE = True
except ImportError as e:
    UI_HELPERS_AVAILABLE = False
    print("Warning: ui_helpers non disponible - " + str(e))

try:
    from algorithms.generic_validators import (
        validate_positive_number, validate_integer, validate_float,
        validate_string, validate_boolean, validate_list, validate_dict,
        validate_range, validate_step, validate_percentage,
        validate_code, validate_email, validate_phone, validate_url, validate_filename,
        validate_required_params, validate_dependency, validate_consistency,
        validate_dimension, validate_load, validate_concrete_class,
        validate_steel_class, validate_exposure_class,
        validate_form_input, PROJECT_SCHEMA, format_validation_errors
    )
    VALIDATORS_AVAILABLE = True
except ImportError as e:
    VALIDATORS_AVAILABLE = False
    print("Warning: generic_validators non disponible - " + str(e))