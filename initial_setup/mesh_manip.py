#import OSLib
#import scipy.ndimage.interpolation as inter
import matplotlib
print(matplotlib.get_backend())
#matplotlib.use('Agg')
from matplotlib import pyplot as pp
import numpy as np
import signal, time
#import sys, time, msvcrt
#from scipy.ndimage import rotate
#import matplotlib
print(matplotlib.get_backend())
import os
from collections import OrderedDict
import json
import picamera

# def imLoadRaw3d(fid, width, height, depth, dtype=np.uint8, order='xyz'):
#
#     slika = np.fromfile(fid, dtype=dtype)
#
#     if order == 'xyz':
#         slika.shape = [depth, height, width]
#
#     # ...
#     elif order=='yxz':
#         slika.shape = [height, width, depth]
#         #slika = slika.transpose([1, 2, 0])
#
#     elif order == 'zyx':
#         # Indeksi osi: [ 0  1  2]
#         slika.shape = [width, height, depth]
#         slika = slika.transpose([2, 1, 0])
#     else:
#         raise ValueError('Vrstni red ima napačno vrednost.' \
#                          'Dopustne vrednosti so \'xyz\' ali \'zyx\'.')
#     return slika
#
#
#
# def ptTransform2d(T, x, y, inverse=False):
#     x = np.asarray(x, np.float64)
#     y = np.asarray(y, np.float64)
#     T = np.asarray(T, np.float64)
#     xt = np.asarray(x, np.uint16)
#     yt = np.asarray(y, np.uint16)
#
#     R = np.vstack([x.flatten(), y.flatten(), np.ones([x.size])])
#
#     if inverse:
#         Rt = np.linalg.solve(T, R)  # resi linearen sistem enačb tipa: T*Rt=R
#
#     else:
#         Rt = np.dot(T, R)
#
#     xt = Rt[0] / Rt[2]
#     yt = Rt[1] / Rt[2]
#     xt.shape, yt.shape = x.shape, y.shape
#     return xt.astype(np.uint8), yt.astype(np.uint8)
#     return xt, yt
#
#
# def rotate_bin(image, rot, image_value):
#     y, x = image.shape
#     x_center = x//2
#     y_center = y//2
#
#     fi = np.deg2rad(rot)
#     Tr = np.array([[np.cos(fi), -np.sin(fi), 0.0],
#                    [np.sin(fi), np.cos(fi), 0.0],
#                    [0.0, 0.0, 1.0]])
#
#     idx = np.where(image==image_value)
#
#     # xt, yt
#     idx_x, idx_y = idx[1]-x, idx[0]-y
#     xt, yt = ptTransform2d(Tr, idx_x, idx_y)
#     xt = xt + x
#     yt = yt + y
#     new_image = np.zeros((y, x),dtype=np.uint8)
#     new_idx = (yt, xt)
#     new_image[new_idx] = image_value
#
#     return new_image
#
# def shift_picture(img, dx, dy):
#     non = lambda s: s if s < 0 else None
#     mom = lambda s: max(0, s)
#     newImg = np.zeros_like(img)
#     newImg[mom(dy):non(dy), mom(dx):non(dx)] = img[mom(-dy):non(-dy), mom(-dx):non(-dx)]
#     return newImg
#
# def scale_picture(image, scale_x, scale_y, image_value):
#     y, x = image.shape
#     scaled_img = np.zeros((y,x),dtype=np.uint8)
#     Tx = np.array([[scale_x, 0.0, 0.0],
#                    [0.0, scale_y, 0.0],
#                    [0.0, 0.0, 1.0]])
#
#     idx = np.where(image==image_value)
#     idx_x, idx_y = idx[1], idx[0]
#     xt, yt = ptTransform2d(Tx, idx_x, idx_y)
#     new_idx = (yt, xt)
#     scaled_img[new_idx] = image_value
#
#     return scaled_img
#
# def get_closest(image, t):
#     idx = np.where(image==255)
#     length = len(idx[0])
#     dist_matrix = np.empty(len(idx[0]))
#     y  = int(t[0][1])
#     x = int(t[0][0])
#     for i in range(length):
#         valx = idx[1][i]
#         valy = idx[0][i]
#         dist_matrix[i] = np.sqrt(pow(abs(x - valx), 2) + pow(abs(y - valy), 2))
#     tx = idx[1][np.argmin(dist_matrix)]
#     ty = idx[0][np.argmin(dist_matrix)]
#     return tx, ty
#
# def get_input_command():
#     command = input('Enter Comand')
#     #print(command)
#
#     fi_sensitivity = 360 / 720
#     scale_sensitivity = 0.97
#     shift_sensitivity = 1
#
#     dxx, dyy, dff, s = 0, 0, 0, 0
#     if command == 'a':
#         dxx = -1 * shift_sensitivity
#     elif command == 'd':
#         dxx = 1 * shift_sensitivity
#     else:
#         dxx = 0 * shift_sensitivity
#
#     if command == 'w':
#         dyy = -1 * shift_sensitivity
#     elif command == 's':
#         dyy = 1 * shift_sensitivity
#     else:
#         dyy = 0 * shift_sensitivity
#
#     if command == 'r':
#         dff = 1 * fi_sensitivity
#     elif command == 't':
#         dff = -1 * fi_sensitivity
#     else:
#         dff = 0 * fi_sensitivity
#
#     if command == 'o':
#         s = 1 * scale_sensitivity
#     elif command == 'p':
#         s = 1 * scale_sensitivity
#     else:
#         s = 1.0
#
#     return command, dxx,dyy,dff,s
#
# class Mask:
#     def __init__(self):
#         self.config_file = os.path.join(os.path.dirname(__file__), "MVC2", "Masks.json")
#         # self.load(self.config_file)
#
#     def load(self):
#         if os.path.exists(self.config_file):
#             with open(self.config_file, 'r') as f:
#                 data = json.load(f,object_pairs_hook=OrderedDict)
#                 #self.gpios_settings = data['gpio_settings']
#
#     def save(self, to_save, span):
#         data = {
#             "span" : span,
#            "indices": to_save
#         }
#         with open(self.config_file, 'w') as f:
#             json.dump(data, f, indent=4)


#USER CODE HERE
#####################################################################################################################
# mesh_path ='C:/Users/jurema/Documents/Projects/rasperryPi/PI/Obdelava slik/testna_one_mesh/Mesh.jpg'
# mesh = OSLib.imLoadRaw2d(mesh_path, 240, 128,  order = 'xy')
#
# path =  'C:/Users/jurema/Documents/Projects/rasperryPi/PI/Obdelava slik/testna_two/first_pic/Picture5.jpg'
# image = OSLib.imLoadRaw3d(path, 240, 128, 3, order = 'yxz')
###################################################################################################################
# rot = 5
# shift_x = 10
# shift_y = 50
# scale = 0.7
# #mesh_rotate = rotate(mesh, 10, reshape=False)
# mesh_rotate = rotate_bin(mesh, 5, image_value=255)
# mesh_shift = shift_picture(mesh_rotate,shift_x, shift_y)
# mesh_scale = scale_picture(mesh_shift, scale, scale, 255)
# print(np.sum(mesh), np.sum(mesh_rotate))
#
#
#
# pp.figure()
# pp.subplot(221)
# pp.imshow(mesh)
# pp.title("Orig mesh")
# pp.subplot(222)
# pp.imshow(mesh_rotate)
# pp.title("Rotated mesh")
# pp.subplot(223)
# pp.imshow(mesh_shift)
# pp.title("R+Shift mesh")
# pp.subplot(224)
# pp.imshow(mesh_scale)
# pp.title("R+Shift+scale mesh")
# pp.show()



# def readInput( caption, default, timeout = 5):
#     start_time = time.time()
#     sys.stdout.write('%s(%s):'%(caption, default));
#     input = ""
#     while True:
#         if msvcrt.kbhit():
#             chr = msvcrt.getche()
#             if ord(chr) == 13: # enter_key
#                 break
#             elif ord(chr) >= 32: #space_char
#                 input += str(chr)
#         if len(input) == 0 and (time.time() - start_time) > timeout:
#             break
#
#     print ('')  # needed to move to next line
#     if len(input) > 0:
#         return input
#     else:
#         return default

#######################################################################################

class CameraDevice:
    def __init__(self, Xres: int=240, Yres: int=128):
        self.Xres = Xres
        self.Yres = Yres

        self.camera = picamera.PiCamera()
        self.set_camera_parameters(flag=False)
        try:
            # logger.debug("Starting self test")
            # self.self_test()
            pass
        except:
           print("Failed to init Camera")

    def close(self):
        self.camera.close()

    def set_camera_parameters(self, flag=False):
        if flag:
            print("Set parameters. Setting iso and exposure time. Wait 2.5 s")
            self.camera.resolution = (self.Xres, self.Yres)
            self.camera.framerate = 80
            self.camera.brightness = 30
            time.sleep(2)
            self.camera.iso = 1 # change accordingly
            time.sleep(1)
            self.camera.shutter_speed = self.camera.exposure_speed * 3
            self.camera.exposure_mode = 'off'
            g = self.camera.awb_gains
            self.camera.awb_mode = 'off'
            self.camera.awb_gains = g
            time.sleep(0.5)
        else:
            self.camera.resolution = (self.Xres, self.Yres)
            #self.camera.framerate = 80
            time.sleep(1)

    def take_picture(self):
        self.img = np.empty((self.Yres, self.Xres, 3), dtype=np.uint8)
        self.camera.capture(self.img, 'rgb', use_video_port=True)
        print("Took picture")
        return self.img

    def get_picture(self, Idx=0):
        return self.img

    def take_img_to_array_RGB(self, xres=128, yres=80, RGB=0):
        slika = np.empty([xres, yres, 3], dtype=np.uint8)
        self.camera.capture(slika, 'rgb')
        return slika[:, :, RGB]

    def take_img_to_file(self, file_path):
        time.sleep(1)
        self.camera.capture(file_path)



class MeshLoader:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.indices_length=[]
        self.mesh_count = None
        self.success = False
        self.load()


    def load(self, display=True):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                data = json.load(f,object_pairs_hook=OrderedDict)
                self.meshes_dict = data['Meshes']
                self.span = data['span']
                self.Xres = data['Xres']
                self.Yres = data['Yres']
                self.mesh = np.zeros((20, self.Yres, self.Xres), dtype=np.uint8)
                self.construct_mask_array('', display)
                self.success =  True
        else:
            self.success = False
            print("Mesh file does not exist")

    def display_meshes(self):
        pp.pause(0.0001)
        w = np.ceil(np.sqrt(self.mesh_count))
        h = np.ceil(np.sqrt(self.mesh_count))
        pp.figure()
        for i in range(self.mesh_count):
            pp.subplot(int(h),int(w),i+1)
            pp.imshow(self.mesh[i,::,::])
            pp.suptitle(str(i))

        pp.title("Click to continue")
        t = pp.ginput(n=1, timeout=500)
        pp.close()

    def delete_meshes(self):
        self.mesh = np.zeros((20, self.Yres, self.Xres), dtype=np.uint8)
        data = {
            "span": 2,
            "Xres": 240,
            "Yres": 128,
            "Meshes": {}
        }
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=4)
        self.load()


    def construct_mask_array(self, mask_prefix, display):
        print("Existing meshes : ")
        self.mesh_count = len(self.meshes_dict)
        if self.mesh_count==0:
            print('None')
            return False
        # max 50 x 5(x,y,R,G,B) x mask_num( fixed at 20)
        #self.mesh = np.zeros((self.mesh_count, self.Yres, self.Xres), dtype=np.uint8)
        for j in range(self.mesh_count):
            print('\''+str(j)+'\'' +', ')
            mesh_name = mask_prefix + str(j)
            mesh_dict = self.meshes_dict[mesh_name]
            num_of_indices = len(mesh_dict)
            for i in range(num_of_indices):
                x = mesh_dict[i]['x']
                y = mesh_dict[i]['y']
                R = mesh_dict[i]['R']
                G = mesh_dict[i]['G']
                B = mesh_dict[i]['B']
                self.mesh[j,y,x] = 255
            self.indices_length.append(num_of_indices)
        if display==True:
            command = input('Do you want to display meshes y/n ?')
            if command=='y':
                self.display_meshes()

        return True

    def save_reload(self):
        self.load(display=False)

    def save(self, to_save, span):
        data = {
            "span": span,
            "Xres": 240,
            "Yres": 128,
            "Meshes": to_save
        }
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=4)




class MeshCreator:
    def __init__(self):
        self.current_mesh = np.zeros((128,240), dtype=np.uint8)
        self.current_image = None
        self.mesh_num = None
        self.mesh_count = 1
        self.meshes = None
        self.save_file = 'C:/Users/jurema/Documents/Projects/rasperryPi/PI/Obdelava slik/MVC2/Mask.json'
        self.reload_mesh_file = 'C:/Users/jurema/Documents/Projects/rasperryPi/PI/Obdelava slik/MVC2/Mask.json'
        self.reload_image_file = 'C:/Users/jurema/Documents/Projects/rasperryPi/PI/Obdelava slik/testna_two/first_pic/Picture5.jpg'
        self.start()
        self.run()


    def load_mesh(self):
        #file = input("Enter Mesh.json path file")
        file = 'C:/Users/jurema/Documents/Projects/rasperryPi/PI/Obdelava slik/MVC2/Mask.json'
        self.mesh_num = 0
        self.meshes = MeshLoader(file)
        if self.meshes.success==False or self.meshes.mesh_count==0:
            return False
        if self.meshes.mesh_count>1:
            num =  input("Enter number of mesh you want to render")
            self.mesh_num=int(num)
        try:
            self.current_mesh = self.meshes.mesh[self.mesh_num,:,:]
        except:
            print("Mesh number {} does not exist".format(self.mesh_num))

    def load_image(self):
        #file = input("Enter image location")
        file = 'C:/Users/jurema/Documents/Projects/rasperryPi/PI/Obdelava slik/testna_two/first_pic/Picture5.jpg'
        if not os.path.exists(file):
            print("File does not exist. Would you like to take a picture Y/N?")
            command = input()
            if command=='y':
                self.take_new_picture()
                return True
            else:
                return False
        self.current_image = self.imLoadRaw3d(file, 240, 128, 3, order='yxz')

    def save(self):
        #file = input("Enter file path you want to save into")
        mesh_dict = {}
        list = []

        if self.meshes.mesh_count==0:
            idx = np.where(self.new_mesh == 255)
            for i, y in enumerate(idx[0]):
                x = int(idx[1][i])
                y = int(idx[0][i])
                list.append(
                    {"x": x, "y": y, "R": int(self.current_image[y, x, 0]), "G": int(self.current_image[y, x, 1]),
                     "B": int(self.current_image[y, x, 2])})
            mesh_dict["0"] = list
        else:
            self.meshes.mesh[self.mesh_num,::,::] = self.new_mesh
            for j in range(self.mesh_count):
                idx = np.where(self.meshes.mesh[j,::,::] == 255)
                for i, y in enumerate(idx[0]):
                    x = int(idx[1][i])
                    y = int(idx[0][i])
                    list.append(
                        {"x": x, "y": y, "R": int(self.current_image[y, x, 0]), "G": int(self.current_image[y, x, 1]),
                         "B": int(self.current_image[y, x, 2])})
                mesh_dict[str(j)] = list
        data = {
            "span": 2,
            "Xres": 240,
            "Yres": 128,
            "Meshes": mesh_dict
        }
        with open(self.save_file, 'w') as f:
            json.dump(data, f, indent=4)

    def run(self):
        print("Commands :\n lm --> load mesh\n lp --> load picture\n s --> save\n r --> render\n t --> take picture\n p --> show\n q --> quit")
        while True:
            command = self.get_input_command()

            if command=='s':
                self.save()
            if command=='lm':
                self.load_mesh()
            if command=='lp':
                self.load_image()
            if command=='r':
                self.render()
            if command=='p':
                self.display()
            if command=='p':
                self.take_new_picture()
                self.display()
            if command=='q':
                break;

    def reload(self):
        pass

    def start(self):
        self.load_image()
        self.load_mesh()

        x = self.current_mesh.shape[1]
        y = self.current_mesh.shape[0]
        self.new_mesh = np.zeros((y, x), dtype=np.uint8)
        self.empty_mesh = np.zeros((y, x), dtype=np.uint8)
        self.temp_image = np.copy(self.current_image)

        self.new_mesh = self.current_mesh
        #temp_mesh = OSLib.closing(self.new_mesh, level=1, ls=255)
        temp_mesh = self.new_mesh
        idx = temp_mesh == 255
        self.temp_image = np.copy(self.current_image)
        self.temp_image[idx] = 0

    def render (self):
        pp.ion()
        print("Commands :\n d --> delete one idx\n s --> save\n n --> add new\n m --> move one idx\n b --> back")

        while True:
            #pp.pause(0.0001)
            command = self.get_input_command()

            if command == 'n':
                while True:
                    print('Create new point')
                    pp.imshow(self.temp_image)
                    pp.title('Chose new index')
                    t = pp.ginput(n=1, timeout=500)
                    if not t:
                        break
                    self.new_mesh[int(t[0][1]), int(t[0][0])] = 255
                    pp.close()
                    self.display()

            if command == 'm':
                while True:
                    print('Select point to move')
                    pp.imshow(self.temp_image)
                    t = pp.ginput(n=1, timeout=500)
                    if not t:
                        break
                    x, y = self.get_closest(self.new_mesh, t)
                    self.new_mesh[y, x] = 0
                    t = pp.ginput(n=1, timeout=500)
                    pp.close()
                    self.new_mesh[int(t[0][1]), int(t[0][0])] = 255

                    #temp_mesh = OSLib.closing(self.new_mesh, level=1, ls=255)
                    temp_mesh = self.new_mesh
                    idx = temp_mesh == 255
                    self.temp_image = np.copy(self.current_image)
                    self.temp_image[idx] = 0
                    pp.imshow(self.temp_image)
                    pp.show()

            if command == 'd':
                while True:
                    print('Select point to delete')
                    pp.imshow(self.temp_image)
                    t = pp.ginput(n=1, timeout=500)
                    if not t:
                        break
                    x, y = self.get_closest(self.new_mesh, t)
                    self.new_mesh[y, x] = 0
                    pp.close()

                    #temp_mesh = OSLib.closing(self.new_mesh, level=1, ls=255)
                    temp_mesh = self.new_mesh
                    idx = temp_mesh == 255
                    self.temp_image = np.copy(self.current_image)
                    self.temp_image[idx] = 0
                    pp.imshow(self.temp_image)
                    pp.show()

            if command == 's':
                self.save()

            if command == 'b':
                break

            self.display()

    def display(self):
        #temp_mesh = OSLib.closing(self.new_mesh, level=1, ls=255)
        temp_mesh = self.new_mesh
        idx = temp_mesh == 255
        self.temp_image = np.copy(self.current_image)
        self.temp_image[idx] = 0
        pp.imshow(self.temp_image)
        pp.show()

    def get_input_command(self):
        command = input('\nComand :')
        # print(command)

        fi_sensitivity = 360 / 720
        scale_sensitivity = 0.97
        shift_sensitivity = 1
        return command

    def imLoadRaw3d(self, fid, width, height, depth, dtype=np.uint8, order='xyz'):
        slika = np.fromfile(fid, dtype=dtype)

        if order == 'xyz':
            slika.shape = [depth, height, width]
        # ...
        elif order == 'yxz':
            slika.shape = [height, width, depth]
            # slika = slika.transpose([1, 2, 0])

        elif order == 'zyx':
            # Indeksi osi: [ 0  1  2]
            slika.shape = [width, height, depth]
            slika = slika.transpose([2, 1, 0])
        else:
            raise ValueError('Vrstni red ima napačno vrednost.' \
                             'Dopustne vrednosti so \'xyz\' ali \'zyx\'.')
        return slika

    def get_closest(self, image, t):
        idx = np.where(image==255)
        length = len(idx[0])
        dist_matrix = np.empty(len(idx[0]))
        y  = int(t[0][1])
        x = int(t[0][0])
        for i in range(length):
            valx = idx[1][i]
            valy = idx[0][i]
            dist_matrix[i] = np.sqrt(pow(abs(x - valx), 2) + pow(abs(y - valy), 2))
        tx = idx[1][np.argmin(dist_matrix)]
        ty = idx[0][np.argmin(dist_matrix)]
        return tx, ty

    def take_new_picture(self):
        my_camera = CameraDevice()
        self.current_image = my_camera.take_picture()
#######################################################################################

create = MeshCreator()
