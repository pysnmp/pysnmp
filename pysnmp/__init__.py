# http://www.python.org/dev/peps/pep-0396/
__version__ = "6.0.0-rc.6"
# another variable is required to prevent semantic release from updating version in more than one place
main_version = __version__
# backward compatibility
# for pre-release versions, integer casting throws an exception, so the
# pre-release and build metadata parts must be cut off
main_version = __version__.split("-")[0].split("+")[0]
version = tuple(int(x) for x in main_version.split("."))
majorVersionId = version[0]
