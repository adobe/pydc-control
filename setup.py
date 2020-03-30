from os.path import join, dirname
from setuptools import setup, find_packages

__version__ = open(join(dirname(__file__), 'pydc_control/VERSION')).read().strip()

install_requires = (
    'Jinja2>=2.7.2',
    'PyYAML>=5.1.2',
    'requests>=2',
)  # yapf: disable

excludes = (
    '*test*',
) # yapf: disable

setup(name='pydc-control',
      version=__version__,
      license='MIT',
      description='Used to control multiple docker compose projects in a coordinated way',
      author='Brian Saville',
      author_email='bksaville@gmail.com',
      url='http://github.com/bluesliverx/pydc-control',
      platforms=['Any'],
      packages=find_packages(exclude=excludes),
      install_requires=install_requires,
      classifiers=['Development Status :: 4 - Beta',
                   'License :: OSI Approved :: MIT License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.4',
                   'Programming Language :: Python :: 3.5',
                   'Programming Language :: Python :: 3.6'])
