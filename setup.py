from setuptools import setup, find_packages

setup(
    name='itslearning-dl',
    version='0.1',
    py_modules=['itslearning_dl'],
    packages=find_packages(),
    install_requires=[
        'requests',
        'beautifulsoup4',
        'python-dotenv'
    ],
    entry_points={
        'console_scripts': [
            'ildl=itslearning_dl:main',
            'itslearning-dl=itslearning_dl:main'
        ],
    },
)
