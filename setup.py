from setuptools import setup, find_packages
import re


with open("google_workspace/__init__.py", encoding="utf-8") as f:
    version = re.findall(r"__version__ = \"(.+)\"", f.read())[0]


with open("README.md", encoding="utf-8") as f:
    readme = f.read()


with open("requirements.txt", encoding="utf-8") as f:
    requirements = [r.strip() for r in f]


setup(
    name="google-workspace",
    version=version,
    packages=find_packages(),
    url="https://github.com/dermasmid/google-workspace",
    license="MIT",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Cheskel Twersky",
    author_email="twerskycheskel@gmail.com",
    description="A Python wrapper for the google workspace APIs",
    keywords="gmail gmail-api drive google-drive google-drive-api api-wrapper python3 python",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=requirements,
    python_requires=">=3.6",
)
