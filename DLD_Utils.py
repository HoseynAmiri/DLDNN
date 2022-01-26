import os
import time
import pickle
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
from scipy.interpolate import griddata
from math import atan
from shapely import affinity
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from descartes import PolygonPatch
import particle_trajectory as ptj

'''
DLD_Utils provides a necessary tasks from creating pillar
to handling results coming from the generated data
'''


class DLD_Utils:
    def __init__(self, resolution=(100, 100), pillar_type='circle'):

        self.pillar_type = pillar_type
        self.resolution = resolution
        self.grid_data = self.grid()

    def grid(self, grid_size=None):

        if not grid_size:
            grid_size = self.resolution

        x_grid_size = grid_size[0]
        y_grid_size = grid_size[1]

        xx = np.linspace(0, 1, x_grid_size)
        yy = np.linspace(0, 1, y_grid_size)
        x_grid, y_grid = np.meshgrid(xx, yy)

        dx = xx[1] - xx[0]
        dy = yy[1] - yy[0]

        return x_grid, y_grid, dx, dy

    def pillar(self, D, pillar_type=None, pillar_org=(0, 0)):
        # First makes one pillar
        if not pillar_type:
            pillar_type = self.pillar_type

        geometry_types = {'circle': 0, 'polygon': 1}
        if geometry_types.get(pillar_type) == 0:
            pillar = Point(pillar_org).buffer(D/2)
        else:
            pillar = Polygon([d for d in D])

        return pillar

    def pillars(self, pillar1, D, N, G_X, G_R=1):

        pillar2 = affinity.translate(pillar1, xoff=D+G_X, yoff=(D+G_X*G_R)/N)
        pillar3 = affinity.translate(pillar1, yoff=(D+G_X*G_R))
        pillar4 = affinity.translate(pillar2, yoff=(D+G_X*G_R))

        pillar1s = affinity.skew(
            pillar1, ys=-atan(1/N), origin=(0, 0), use_radians=True)
        pillar2s = affinity.skew(
            pillar2, ys=-atan(1/N), origin=(0, 0), use_radians=True)
        pillar3s = affinity.skew(
            pillar3, ys=-atan(1/N), origin=(0, 0), use_radians=True)
        pillar4s = affinity.skew(
            pillar4, ys=-atan(1/N), origin=(0, 0), use_radians=True)

        pillar1ss = affinity.scale(
            pillar1s, xfact=1/(D+G_X), yfact=1/(D+G_X*G_R), zfact=1.0, origin=(0, 0))
        pillar2ss = affinity.scale(
            pillar2s, xfact=1/(D+G_X), yfact=1/(D+G_X*G_R), zfact=1.0, origin=(0, 0))
        pillar3ss = affinity.scale(
            pillar3s, xfact=1/(D+G_X), yfact=1/(D+G_X*G_R), zfact=1.0, origin=(0, 0))
        pillar4ss = affinity.scale(
            pillar4s, xfact=1/(D+G_X), yfact=1/(D+G_X*G_R), zfact=1.0, origin=(0, 0))

        return [pillar1ss, pillar2ss, pillar3ss, pillar4ss]

    def pillar_mask(self, grid, pillar):

        grid_points = np.array([grid[0].flatten(), grid[1].flatten()]).T
        grid_Points = [Point(p) for p in grid_points.tolist()]

        def contains(point):

            inside = False
            for p in pillar:
                if p.contains(point):
                    inside = True

            return inside

        mask = filter(contains, grid_Points)
        idx = list(filter(lambda i: contains(
            grid_Points[i]), range(len((grid_Points)))))
        xy_mask = [p.coords[0] for p in mask]

        return np.array(xy_mask), idx

    def add_mask(self, data, xy_mask, D, N, G_X, G_R=1, mask_with=0):

        x, y = self.square2parall(
            xy_mask[:, 0], xy_mask[:, 1], 1/N, D, G_X, G_R=G_R)
        xy_mask = np.concatenate(([x], [y])).T

        empty = np.empty((xy_mask.shape[0], data.shape[1]-xy_mask.shape[1]))
        empty[:] = mask_with

        mask_data = np.concatenate((xy_mask, empty), axis=1)

        return np.concatenate((data, mask_data))

    def insert_mask(self, data, idx, mask_with=0):

        if len(data.shape) >= 2:
            shape = data.shape
            data = data.flatten()
            data[idx] = mask_with
            return data.reshape(shape)
        else:
            data[idx] = mask_with
            return data

    def parall2square(self, x, y, slope, D, G_X, G_R=1):
        # Domain shear transformation from parallelogram to rectangular
        x_mapped = x
        y_mapped = y - slope * x

        # Domain transformation from rectangular to unitariy square
        X_mapped_MAX = D + G_X
        Y_mapped_MAX = D + G_X * G_R

        x_mapped = x_mapped / X_mapped_MAX
        y_mapped = y_mapped / Y_mapped_MAX

        return x_mapped, y_mapped

    def square2parall(self, x, y, slope, D, G_X, G_R=1):

        X_MAX = D + G_X
        Y_MAX = D + G_X * G_R

        # Scaling square to rectangle
        x_mapped = x * X_MAX
        y_mapped = y * Y_MAX

        # Mapping rectangle to parallelogram by shear transformation
        x_mapped = x_mapped
        y_mapped = y_mapped + slope * x_mapped

        return x_mapped, y_mapped

    def interp2grid(self, x_mapped, y_mapped, data, x_grid, y_grid, method='linear', recover=False):
        # Interpolation of mapped data to x & y grid
        mapped = np.array([x_mapped, y_mapped]).T
        data_interp = griddata(mapped, data, (x_grid, y_grid), method=method)

        if recover:
            nearest = griddata(
                mapped, data, (x_grid, y_grid), method='nearest')
            data_interp[np.isnan(data_interp)] = nearest[np.isnan(data_interp)]

        return data_interp

    def recover_uv(self, u, recover_with=0):

        sub_u_h = u[:, -3:]
        sub_u_f_h = np.flip(u, axis=1)[:, -3:]
        sub_u_v = u[-3:, :]
        sub_u_f_v = np.flip(u, axis=0)[-3:, :]

        sub_u_h[np.isnan(sub_u_h)] = sub_u_f_h[np.isnan(sub_u_h)]
        sub_u_v[np.isnan(sub_u_v)] = sub_u_f_v[np.isnan(sub_u_v)]

        u[:, -3:] = sub_u_h
        u[-3:, :] = sub_u_v

        u[np.isnan(u)] = recover_with

        return u

    def compare_plots(self, data1, data2, figsize=(8, 6)):

        x, y, u, v = data1[0], data1[1], data1[2], data1[3]
        x_new, y_new, u_new, v_new = data2[0], data2[1], data2[2], data2[3]

        fig = plt.figure(figsize=figsize)
        ax1 = fig.add_subplot(2, 2, 1)
        ax1.set_xlabel('$x$')
        ax1.set_ylabel('$y$')
        ax1.set_title("$\psi$ (before)")
        plt.scatter(x, y, s=0.1, c=u)
        plt.colorbar()

        ax2 = fig.add_subplot(2, 2, 2)
        ax2.set_title("p (before)")
        plt.scatter(x, y, s=0.1, c=v)
        plt.colorbar()

        ax3 = fig.add_subplot(2, 2, 3)
        ax3.set_title("$\psi$ (after)")
        plt.scatter(x_new, y_new, s=0.1, c=u_new)
        plt.colorbar()
        ax4 = fig.add_subplot(2, 2, 4)
        ax4.set_title("p (after)")
        plt.scatter(x_new, y_new, s=0.1, c=v_new)
        plt.colorbar()

        plt.show()

    def gradient(self, psi, dx, dy, recover=True, plot=False, figsize=(8, 4)):

        u = np.gradient(psi, dy, axis=0)
        v = -np.gradient(psi, dx, axis=1)

        if recover:
            u = self.recover_uv(u)
            v = self.recover_uv(v)

        if plot:
            fig, axes = plt.subplots(1, 2, figsize=figsize)
            fig.subplots_adjust(left=0.1, wspace=0.5)

            im = axes[0].imshow(np.flip(u, axis=0), extent=[
                                0, 1, 0, 1], cmap='rainbow')
            axes[0].set_title("u [m/s]")
            axes[0].set(xlabel="$x*$", ylabel="$y*$")

            xc = axes.flat[0].get_position().x0
            wc = axes.flat[0].get_position().width
            yc = axes.flat[0].get_position().y0
            hc = axes.flat[0].get_position().height
            cbar_ax = fig.add_axes([xc+wc+0.02, yc, 0.02, hc])
            fig.colorbar(im, cax=cbar_ax)

            im = axes[1].imshow(np.flip(v, axis=0), extent=[
                                0, 1, 0, 1], cmap='rainbow')
            axes[1].set_title("v [m/s]")
            axes[1].set(xlabel="$x*$", ylabel="$y*$")

            cbar_ax = fig.add_axes([0.92, yc, 0.02, hc])
            fig.colorbar(im, cax=cbar_ax)

            plt.show()

        return u, v

    def box_delete(self, array, MIN, MAX):
        
        min_array = np.min(array, axis=1)
        array_minimized = array[MIN <= min_array]
        max_array_minimized = np.max(array_minimized, axis=1)

        return array_minimized[max_array_minimized <= MAX]

    def wallfunc(self, grid, pillar, plot=True):

        X = np.array([])
        Y = np.array([])
        for p in pillar: 
            x, y = p.exterior.xy
            xp = np.asarray(x)
            yp = np.asarray(y)
            X = np.append(X, xp)
            Y = np.append(Y, yp)
            
        pillars_coord = np.array((X, Y)).T
        pillars_coord = self.box_delete(pillars_coord, 0, 1)
        _, mask_idx = self.pillar_mask(grid, pillar)
        
        domain_idx = np.setdiff1d(np.arange(len(grid[0].flatten())), mask_idx)
        domain_x_grid = grid[0].flatten()[domain_idx]
        domain_y_grid = grid[1].flatten()[domain_idx]
        
        wall_distance = np.zeros_like(grid[0])
        size_x = grid[0].shape[0]
        size_y = grid[0].shape[1]
        for x, y in zip(domain_x_grid, domain_y_grid):
            r = int(y * size_y)
            if r == size_y:
                r -= 1
            
            c = int(x * size_x)
            if c == size_x:
                c -= 1
            
            wall_distance[r, c] = np.amin(np.sqrt((x-pillars_coord[:, 0])**2 + (y-pillars_coord[:, 1])**2))

        if plot:
            fig = plt.figure()
            ax = plt.gca()
            im = plt.imshow(np.flip(wall_distance, axis=0), extent=[0, 1, 0, 1])
            xc = ax.get_position().x0
            wc = ax.get_position().width
            yc = ax.get_position().y0
            hc = ax.get_position().height
            cbar_ax = fig.add_axes([xc+wc+0.02, yc, 0.02, hc])
            fig.colorbar(im, cax=cbar_ax)

            plt.show()

        return wall_distance

    def simulate_particle(self, dp, uv, pillars, start_point, periods=1, plot=False, figsize=(9, 4)):

        shape = uv[0].shape
        xx = np.linspace(0, 1, shape[0])
        yy = np.linspace(0, 1, shape[1])
        x_grid, y_grid = np.meshgrid(xx, yy)

        dx = xx[1] - xx[0]
        dy = yy[1] - yy[0]

        wall_distance = self.wallfunc((x_grid, y_grid), pillars, plot=False)
        ny, nx = self.gradient(wall_distance, dx, dy, recover=True, plot=False)

        dist_mag = np.ma.sqrt(nx**2 + ny**2)
        nx = - nx / dist_mag 
        ny = ny / dist_mag

        stream = []
        for i in range(periods):
            stream.append(ptj.streamplot((x_grid, y_grid), uv, (nx, ny), pillars, dp, start_point))

            if stream[i][-1, 0] >= 0.99:
                start_point = stream[i][-1, :] - [1, 0]
            elif stream[i][-1, 1] <= 0.01:
                start_point = stream[i][-1, :] + [0, 1]

        if plot:
            fig = plt.figure(figsize=figsize)
            fig.add_subplot(1, 2, 1)
            periods = len(stream)
            step_data = np.zeros((periods, 2))
            for i in range(periods):
                plt.plot(stream[i][:, 0], stream[i][:, 1], color=(
                    0.1, 0.2, 0.5, (i/periods+0.1)/1.1))

                step_data[i] = [stream[i][0, 1], stream[i][-1, 1]]

            plt.xlim([0, 1])
            plt.ylim([0, 1])

            ax = plt.gca()
            for pillar in pillars:
                ax.add_patch(PolygonPatch(pillar, fc='red'))
                ax.add_patch(PolygonPatch(pillar.buffer(
                    dp/2).difference(pillar), fc='white', ec='#999999'))

            fig.add_subplot(1, 2, 2)
            plt.plot(step_data[:, 0], step_data[:, 1])
            plt.xlim([0, 1])
            plt.ylim([0, 1])

            plt.show()

        return stream

    def compile_data(self, grid_size=None):

        if not grid_size:
            grid_size = self.resolution

        x_grid_size = grid_size[0]
        y_grid_size = grid_size[1]

        xx = np.linspace(0, 1, x_grid_size)
        yy = np.linspace(0, 1, y_grid_size)
        x_grid, y_grid = np.meshgrid(xx, yy)

        directory = os.getcwd() + "\\Data"

        folders = [name for name in os.listdir(
            directory) if os.path.isdir(os.path.join(directory, name))]

        dataset_u = []
        dataset_v = []
        labels = []
        pbar1 = tqdm(total=len(folders), position=0, leave=True)
        for folder in folders:
            folder_dir = directory + "\\" + folder
            filesname = [os.path.splitext(filename)[0]
                         for filename in os.listdir(folder_dir)]

            pbar1.update(1)
            time.sleep(0.1)

            pbar2 = tqdm(total=len(filesname), position=0, leave=True)
            for name in filesname:
                data = np.genfromtxt(
                    folder_dir + "\\" + name + ".csv", delimiter=",")
                data = np.nan_to_num(data)

                label = list(map(float, name.split('_')))
                d, n, g, re = label[0], label[1], label[2], label[3]

                labels.append(label)

                x_mapped, y_mapped = self.parall2square(
                    data[:, 0], data[:, 1], 1/n, d, g)
                u_mapped, v_mapped = self.parall2square(
                    data[:, 2], data[:, 3], 1/n, d, g)

                u_interp = self.interp2grid(x_mapped, y_mapped, u_mapped,
                                            x_grid, y_grid)
                v_interp = self.interp2grid(x_mapped, y_mapped, v_mapped,
                                            x_grid, y_grid)

                # Make dataset
                dataset_u.append(u_interp)
                dataset_v.append(v_interp)

                pbar2.update(1)
                time.sleep(0.1)

        return (np.array(dataset_u), np.array(dataset_v), np.array(labels))

    def save_data(self, data, name='data'):
        with open(name+".pickle", "wb") as f:
            pickle.dump(data, f)

    def load_data(self, name='data'):
        with open(name+".pickle", "rb") as f:
            return pickle.load(f)
