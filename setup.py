from setuptools import setup

description = (
    "Selenium Chrome replacement with anti-detection patches; this fork adds proxy support (local forwarder, proxy_server=)."
)

fd = open("README.md", "r")
long_desc = fd.read()
fd.close()

setup(
    name="undetected-chromedriver",
    version='3.6.3',
    packages=["undetected_chromedriver"],
    install_requires=[
        "selenium>=4.18.1",  # Updated to latest as of Mar 2024
        "requests>=2.31.0",  # Updated to latest as of Mar 2024
        "websockets>=12.0",  # Updated to latest as of Mar 2024
        "packaging>=23.0", # Specify a recent version
    ],
    # Examples live under example/; they are not package data.
    url="https://github.com/ultrafunkamsterdam/undetected-chromedriver",
    license="GPL-3.0",
    author="BBMM Software",
    author_email="tudor@bbmmsoftware.com",
    description=description,
    long_description=long_desc,
    long_description_content_type="text/markdown",
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12", # Assuming 3.12 is also supported
        "Programming Language :: Python :: 3.13",
    ],
)