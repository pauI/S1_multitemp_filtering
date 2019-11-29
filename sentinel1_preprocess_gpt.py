# -*- coding: utf-8 -*-
"""
@author: Paul Meurice, INRAE - UMR BAGAP, 2019

Preprocessing of Sentinel-1 GRD data from a single orbit using SNAP GPT command line tool

- unzip sentinel-1 files from the "downloads" folder,
- apply preprocessings (radiometric and geometric calibration),
- cut the images in tiles
- apply Lee-Sigma multi-temporal filtering,
- convert images in GTiff format in the "results" directory.

scritp and associated xml files should be placed in home_dir

"""

import os,sys,subprocess
import zipfile,shutil
from time import gmtime, strftime
from osgeo import ogr,gdal


"""
 Parameters
"""

# path to gdal_calc.py
sys.path.append('~/AppData/Local/Continuum/anaconda3/envs/snappy/Lib/site-packages/GDAL-2.2.4-py2.7-win-amd64.egg-info/scripts/')
import gdal_calc

# path to gpt.exe in SNAP directory
GPTcmd='C:/Program Files/snap/bin/gpt'

# root data directory
home_dir='~/Documents/Master/Projet pro/'
os.chdir(home_dir)
# multipolygon of the study area
empriseShp = "bretagne_crop.shp"

# grid file : will be generated if not existing
gridShp = "grid.shp"
GRID_X=8
GRID_Y=6

# directory of downloaded GRD zipped files from a single orbit
download_path = "download/"
# generated directories inside root data directory :
# temporary directories
preproc_path = "preprocessings/"
tiles_path = "tiles/"
# result directory
result_path = "result/"



"""
 Fonctions
"""

# log function
def print_(chaine):
    print(strftime("%H:%M:%S", gmtime())+":"+chaine)

"""
    creation of a nx*ny tiles grid on the shapefile's extent,
    keeping only tiles that overlap the shape
"""
def createGrid(shapefile,nx,ny):
    # create grid and save to a new Shapefile
    # 
    
    # region of interest
    dr = ogr.GetDriverByName("ESRI Shapefile")
    shp=dr.Open(shapefile,0)
    layer=shp.GetLayer()
    f=layer.GetNextFeature()
    shape=f.GetGeometryRef()

    # extent definition
    extent = layer.GetExtent()
    x_left=extent[0]
    x_right=extent[1]
    y_top=extent[3]
    y_bottom=extent[2]
    height = y_top-y_bottom
    width = x_right - x_left
    w=width/nx
    h=height/ny
    
    # Create the output shapefile
    outDriver = ogr.GetDriverByName("ESRI Shapefile")
    outDataSource = outDriver.CreateDataSource(gridShp)
    outLayer = outDataSource.CreateLayer("grid", geom_type=ogr.wkbPolygon)
    
    # Add an ID field
    idField = ogr.FieldDefn("id", ogr.OFTInteger)
    iField = ogr.FieldDefn("i", ogr.OFTInteger)
    jField = ogr.FieldDefn("j", ogr.OFTInteger)
    outLayer.CreateField(idField)
    outLayer.CreateField(iField)
    outLayer.CreateField(jField)
    
    # Create the feature and set values
    featureDefn = outLayer.GetLayerDefn()

    id=0
    # loop on all rects of the grid to keep only those in which there is data
    for i in range(nx):             
        x = x_left+i*w
        for j in range(ny):
            y=y_bottom+j*h
            # is there an intersection between rect and ROI?
            # Create ring
            ring = ogr.Geometry(ogr.wkbLinearRing)
            ring.AddPoint(x,y)
            ring.AddPoint(x+w,y)
            ring.AddPoint(x+w,y+h)
            ring.AddPoint(x,y+h)
            ring.AddPoint(x,y)
    
            # Create polygon
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            if not poly.Intersects(shape):
                continue
    
            feature = ogr.Feature(featureDefn)
            feature.SetGeometry(poly)
            feature.SetField("id", id)
            feature.SetField("i", i)
            feature.SetField("j", j)
            outLayer.CreateFeature(feature)
            feature = None
            id=id+1
    
    # Save and close DataSource
    outDataSource = None
        

#Now loop through all Sentinel-1 data sub folders that are located within a super folder (of course, make sure, that the data is already unzipped):

pols = ['VV','VH']
    

"""
    Calibration of images successive images from a single orbit
    With successive SNAP steps :
        SliceAssembly : assembly  only if more than one image
        Apply-Orbit-File
        Calibration
        Terrain-Correction
        
"""

def calibrate(*files):
    print_("calibrate...")
    timestamp = files[0].split("_")[-5] 
    date=timestamp[:8]
    print_('output : '+date)
    if len(files)==1:
        subprocess.check_call([GPTcmd,'calibration.xml',
                               '-Psource='+files[0],
                           '-Poutput='+preproc_path+date])
    else:
        subprocess.check_call([GPTcmd,'assembly_and_calibration.xml',
                           '-Poutput='+preproc_path+date]+list(files))
    
    print_("   done")


"""
    Date conversion from ddMmmyyyy to yymmdd
"""
def translateDate(ddMmmyyyy):
    month={'Jan':'01',
          'Feb':'02',
          'Mar':'03',
          'Apr':'04',
          'May':'05',
          'Jun':'06',
          'Jul':'07',
          'Aug':'08',
          'Sep':'09',
          'Oct':'10',
          'Nov':'11',
          'Dec':'12'}
    return ddMmmyyyy[-4:]+mois[ddMmmyyyy[2:5]]+ddMmmyyyy[:2]



"""
 Main script
"""


if __name__ == '__main__':

    # init
    if not os.path.exists(preproc_path):
        os.mkdir(preproc_path)
    if not os.path.exists(preproc_path+'done.txt'):
        open(preproc_path+'done.txt', "a").close()
    if not os.path.exists(tiles_path):
        os.mkdir(tiles_path)
        
    if not os.path.exists(gridShp):
        createGrid(empriseShp,nx=GRID_X,ny=GRID_Y)
      
    files={}
    # preprocessings
    for file in os.listdir(download_path):  
        if file.endswith(".zip"):
            print_("file : "+file)
            
            with open(preproc_path+'done.txt', "r+") as done_list:
                for ligne in done_list:
                    if file in ligne:
                        break
                else:
                   # unzip
                    print_("...unzip")
                    with zipfile.ZipFile(download_path+file,"r") as zip_ref:
                        zip_ref.extractall(preproc_path)
                    print_("unziped!")
                    done_list.write(file+'\n')

            timestamp = file.split("_")[4] 
            date=timestamp[:8]
            if os.path.isfile(preproc_path+date+'.dim'):
                continue
            f=preproc_path+file[:-4]+".SAFE/" + "manifest.safe"
            if date not in files:
                files[date]=[f]
            else:
                files[date].append(f)
    for d,list_files in files:
        calibrate(*list_files)

            
    # grid
    
    dates=[]
    for file in os.listdir(preproc_path):  
        if file.endswith(".dim"):
            date=file[:8]
            dates.append(date)
            print_("fichier : "+file)
            shp=ogr.Open(gridShp)
            gridLayer=shp.GetLayer(gridShp[:-4])
            for tuile in gridLayer:
                path = tiles_path+tuile.GetFieldAsString('i')+'_'+tuile.GetFieldAsString('j')
                if not os.path.exists(path):
                    os.mkdir(path)
                destination = path+'/' + date + '.dim'
                print_('destination : '+destination)
                georegion = tuile.GetGeometryRef().ExportToWkt().replace(" 0","")
                subprocess.check_call([GPTcmd,'subset.xml',
                                       '-Pinput='+preproc_path+file,
                                       '-Pgeoregion='+georegion,
                                       '-Poutput='+destination])
            
    
    # multitemporal filter
    shp=ogr.Open(gridShp)
    gridLayer=shp.GetLayer(gridShp[:-4])
    for tuile in gridLayer:
        path = tiles_path+tuile.GetFieldAsString('i')+'_'+tuile.GetFieldAsString('j')
        print_('tuile : '+path)
        entrees=[path+'/'+dates[i]+'.dim' for i in range(len(dates))]
        subprocess.check_call([GPTcmd,'filter.xml']+
                               ['-Poutput='+path+'/Sigma0_filtered',
                                '-PoutputLog='+path+'/Sigma0_filtered_db']+
                               entrees)
        for e in entrees:
            os.remove(e)
            shutil.rmtree(e[:-3]+"data")
        
    
    
    
               
    # tiles reorganisation
    for dirLoc in os.listdir(tiles_path):
        if len(dirLoc)==3 and dirLoc[1]=='_':
            # create the corresponding path
            path=result_path+dirLoc+'/'
            if not os.path.exists(path):
                os.mkdir(path)
            src_path=tiles_path+dirLoc+'/Sigma0_filtered_db.data/'
            # going through the images
            liste_vv={}
            liste_vh={}            
            for file in os.listdir(src_path):
                if file.endswith('.img'):
                    date=translateDate(file[-16:-7])
                    pol=file[7:9]
                    if pol=='VV':
                        liste_vv[date]=file
                    else:
                        liste_vh[date]=file
            # vv-vh calculation and GTiff conversion
            for (date,vh) in liste_vh.items():
                vv = liste_vv[date]
                output_vv=path+'sigma0_db_vv_'+dirLoc+'_'+date+'.tif'
                output_vh=path+'sigma0_db_vh_'+dirLoc+'_'+date+'.tif'
                output_vvvh=path+'sigma0_db_vvvh_'+dirLoc+'_'+date+'.tif'
                gdal_calc.Calc( calc="B-A", A = src_path+vh, B=src_path+vv, outfile=output_vvvh,overwrite=True)
                gdal.Translate(output_vh,src_path+vh, format="GTiff")
                gdal.Translate(output_vv,src_path+vv, format="GTiff")
            print_('rm '+tiles_path+dirLoc)
            shutil.rmtree(tiles_path+dirLoc)
    
