"""Compatibility shim for the owner's pre-PEP-660 pip.

Canonical project metadata remains in pyproject.toml.
"""

from setuptools import find_packages, setup


setup(
    name="stellaris-mod-translator",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.9",
)
