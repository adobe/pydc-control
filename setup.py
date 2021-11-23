from os.path import join, dirname
from setuptools import setup, find_packages


with open(join(dirname(__file__), 'pydc_control/VERSION')) as fobj:
    version = fobj.read().strip()
with open(join(dirname(__file__), 'README.md')) as fobj:
    long_description = fobj.read().strip()

setup(
    name='pydc-control',
    version=version,
    license='MIT',
    description='Used to control multiple docker compose projects in a coordinated way.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Adobe',
    author_email='noreply@adobe.com',
    url='https://github.com/adobe/pydc-control',
    platforms=['Any'],
    packages=find_packages(exclude=('*test*',)),
    install_requires=(
        'Jinja2>=2.7.2',
        'PyYAML>=5.1.2',
        'requests>=2',
    ),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],

)
