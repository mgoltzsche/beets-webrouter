import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='beets-webrouter',
    version='0.5.0',
    author='Max Goltzsche',
    description='Serve multiple beets APIs on the same IP/port using a single command',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/mgoltzsche/beets-webrouter',
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    install_requires=[
        'beets',
        'fastapi',
        'flask',
        'uvicorn',
    ]
)
