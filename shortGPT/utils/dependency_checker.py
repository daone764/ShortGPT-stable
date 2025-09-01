import pkg_resources

def check_dependencies():
    """
    Checks for required dependencies and returns a list of missing ones.
    """
    required_libs = ['requests', 'moviepy', 'gradio']  # Add more as needed
    missing = []
    for lib in required_libs:
        try:
            pkg_resources.get_distribution(lib)
        except pkg_resources.DistributionNotFound:
            missing.append(lib)
    return missing
