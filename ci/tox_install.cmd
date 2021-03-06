#!/bin/bash -eE
:<<"::batch"
@echo off
conda install --prefix=%1 --yes numpy six
for /f "tokens=1,* delims= " %%a in ("%*") do set ALL_BUT_FIRST=%%b
pip install %ALL_BUT_FIRST%
goto :end
::batch
conda install --prefix=$1 --yes numpy six
pip install ${@:2}
exit $?
:<<"::done"
:end
::done
