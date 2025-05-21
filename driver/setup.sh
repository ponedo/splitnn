git clone https://github.com/KarypisLab/METIS.git
git clone https://github.com/KarypisLab/GKlib.git

cp GKlib_Makefile GKlib/
cd GKlib
make config prefix=~/.local
make -j8
make install

cd METIS
sed -i '/add_library(metis ${METIS_LIBRARY_TYPE} ${metis_sources})/ s/$/\ntarget_link_libraries(metis GKlib)/' libmetis/CMakeLists.txt
make config shared=1 cc=gcc prefix=~/.local

echo 'export METIS_DLL=~/.local/lib/libmetis.so' >> ~/.bashrc
source ~/.bashrc