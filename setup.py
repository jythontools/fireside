import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, find_packages
from clamp.commands import clamp_command

setup(
    name = "fireside",
    version = "0.3",
    packages = find_packages(),
    install_requires = ["clamp"],
    dependency_links=["git+https://github.com/jythontools/clamp.git"],
    tests_require = ["mock", "nose", "WebOb"],
    test_suite = "nose.collector",
    clamp = {
        "modules": ["fireside"]
    },
    cmdclass = { "install": clamp_command }
)
