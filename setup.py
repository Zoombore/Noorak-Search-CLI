#!/usr/bin/env python3
"""Noorak Search CLI — setup.py"""
from setuptools import setup, find_packages

setup(
    name="noorak-search-cli",
    version="2.0.0",
    description="Autonomous deep research CLI — any tool-capable AI model can search, fetch, and write reports via tool-calling loops.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Zoombore",
    author_email="zoombore@users.noreply.github.com",
    url="https://github.com/Zoombore/Noorak-Search-CLI",
    packages=find_packages(include=["engine", "engine.*", "lfe", "lfe.*"]),
    package_dir={"engine": "engine", "lfe": "lfe"},
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
    ],
    entry_points={
        "console_scripts": [
            "noorak=engine.noorak_search:main",
        ],
    },
    zip_safe=False,
)