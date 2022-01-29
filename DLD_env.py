import numpy as np
import matplotlib.pyplot as plt
from math import atan
from shapely import affinity
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from descartes import PolygonPatch
import particle_trajectory as ptj
from DLD_Utils import DLD_Utils as utl
utl=utl()

class DLD_env:
    def __init__(self, pillar, Re, resolution=(100, 100)):

        self.pillar = pillar
        self.Re = Re    
        self.resolution = resolution
        self.x_grid, self.y_grid, self.dx, self.dy = self.grid()
        self.wd = self.wall_distance(plot=False)
    # the grid configuration for this modeling is set in this function 
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
    # Wall distance is function which  measures the minimum distance between each point in the grid 
    # from points on pillars
    def wall_distance(self, plot=True):

        X = np.array([])
        Y = np.array([])
        for pillar in self.pillar.pillars: 
            x, y = pillar.exterior.xy
            xp = np.asarray(x)
            yp = np.asarray(y)
            X = np.append(X, xp)
            Y = np.append(Y, yp)
            
        pillars_coord = np.array((X, Y)).T
        pillars_coord = utl.box_delete(pillars_coord, 0, 1)
        _, mask_idx = self.pillar.to_mask((self.x_grid, self.y_grid))
        
        domain_idx = np.setdiff1d(np.arange(len(self.x_grid.flatten())), mask_idx)
        domain_x_grid = self.x_grid.flatten()[domain_idx]
        domain_y_grid = self.y_grid.flatten()[domain_idx]
        
        wall_distance = np.zeros_like(self.x_grid)
        size_x = self.resolution[0]
        size_y = self.resolution[1]

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
    # this function simulate the particle trajectory by having domain shape, particle size and velocity fields
    def simulate_particle(self, dp, uv, pillars, start_point, periods=1, plot=False, figsize=(9, 4)):

        
        nx, ny = utl.gradient(self.wd, self.dx, self.dy, recover=True)

        dist_mag = np.ma.sqrt(nx**2 + ny**2)
        nx = nx / dist_mag
        ny = ny / dist_mag

        stream = []
        for i in range(periods):
            stream.append(ptj.streamplot((self.x_grid, self.y_grid), uv, (nx, ny), pillars, dp, start_point))

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

# pillar class creates the domain from geometric parameters 
# first one pillar is made then the other three are made accordingly. 
class Pillar:
    def __init__(self, size, N, G_X, G_R=1, pillar_type='circle', origin=(0,0)):

        self.size = size
        self.pillar_type = pillar_type
        
        geometry_types = {'circle': 0, 'square': 1}

        if geometry_types.get(pillar_type) == 0:
            self.pillar = Point(origin).buffer(self.size/2)

        elif geometry_types.get(pillar_type) == 1:
            self.pillar = Polygon([(self.size/2, self.size/2),
                                    (self.size/2, -self.size/2),
                                    (-self.size/2, -self.size/2),
                                    (-self.size/2, self.size/2)])
            
        else: raise ValueError("The input pillar type is invalid")
        
        self.pillar = affinity.translate(self.pillar, xoff=origin[0], yoff=origin[1])
        self.N, self.G_X, self.G_R = N, G_X, G_R
        
        # Other pillars are created automatically
        self.pillars = self.to_pillars()
        
    # The function creating other pillars from the initial one 
    def to_pillars(self):

        pillar1 = self.pillar
        pillar2 = affinity.translate(pillar1, xoff=self.size+self.G_X, yoff=(self.size+self.G_X*self.G_R)/self.N)
        pillar3 = affinity.translate(pillar1, yoff=(self.size+self.G_X*self.G_R))
        pillar4 = affinity.translate(pillar2, yoff=(self.size+self.G_X*self.G_R))

        pillar1s = affinity.skew(
            pillar1, ys=-atan(1/self.N), origin=(0, 0), use_radians=True)
        pillar2s = affinity.skew(
            pillar2, ys=-atan(1/self.N), origin=(0, 0), use_radians=True)
        pillar3s = affinity.skew(
            pillar3, ys=-atan(1/self.N), origin=(0, 0), use_radians=True)
        pillar4s = affinity.skew(
            pillar4, ys=-atan(1/self.N), origin=(0, 0), use_radians=True)

        pillar1ss = affinity.scale(
            pillar1s, xfact=1/(self.size+self.G_X), yfact=1/(self.size+self.G_X*self.G_R), zfact=1.0, origin=(0, 0))
        pillar2ss = affinity.scale(
            pillar2s, xfact=1/(self.size+self.G_X), yfact=1/(self.size+self.G_X*self.G_R), zfact=1.0, origin=(0, 0))
        pillar3ss = affinity.scale(
            pillar3s, xfact=1/(self.size+self.G_X), yfact=1/(self.size+self.G_X*self.G_R), zfact=1.0, origin=(0, 0))
        pillar4ss = affinity.scale(
            pillar4s, xfact=1/(self.size+self.G_X), yfact=1/(self.size+self.G_X*self.G_R), zfact=1.0, origin=(0, 0))

        pillars = [pillar1ss, pillar2ss, pillar3ss, pillar4ss]

        return pillars
    
    # this function finds the grid points outside of the boundary by implementing pillars
    def to_mask(self, grid):

        pillars = self.pillars

        grid_points = np.array([grid[0].flatten(), grid[1].flatten()]).T
        grid_Points = [Point(p) for p in grid_points.tolist()]

        def contains(point):

            inside = False
            for pillar in pillars:
                if pillar.contains(point):
                    inside = True

            return inside

        mask = filter(contains, grid_Points)
        idx = list(filter(lambda i: contains(
            grid_Points[i]), range(len((grid_Points)))))
        xy_mask = [p.coords[0] for p in mask]

        return np.array(xy_mask), idx
