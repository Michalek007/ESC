:: ################# REQUIREMENTS ###################

:: Python must be installed before executing this script

:: ##################################################

@echo OFF
setlocal EnableExtensions DisableDelayedExpansion

:: Install pipenv
py -m pip install pipenv

:: Set value so pipenv will create virtual environment folder in the same directory as project
set PIPENV_VENV_IN_PROJECT=1

:: Create virtual environment if not already exists, install all packages defined in pipfile
py -m pipenv install

