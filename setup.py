from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in bfs_connect/__init__.py
from bfs_connect import __version__ as version

setup(
	name="bfs_connect",
	version=version,
	description="Verarbeiten der Excel-Daten von BFS",
	author="itsdave",
	author_email="   ",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
