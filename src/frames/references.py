

class Frame:
    def __init__(self, width, height):
        self.width = width 
        self.height = height 

    def get_width(self):
        return self.width
    
    def get_height(self):
        return self.height

class FramePipeline:

    def __init__(self, frames, scale_factors):
        """
        frames -> Length N list of Frame objects
        scale_factors -> N x 2 list of x/y conversion factors
        
        
        """
        self.frames = frames
        self.scale_factors = scale_factors

        assert len(self.frames) - 1 == len(self.scale_factors), "Mismatched lengths"
    
    def forward(self, input_coords):
        """
        Run through from the base frame to the next frame, assuming the 0th frame 
        is the base and the last frame is derived
        
        
        """
        res = input_coords

        for (i, scale_factor) in enumerate(self.scale_factors):
            res[0], res[1] = res[0] * scale_factor[0], res[1] * scale_factor[1]

        return res 
        
    def backward(self, output_coords):
        """
        Run through from the base frame to the next frame, assuming the 0th frame 
        is the base and the last frame is derived
        
        
        """
        res = output_coords 

        for (i, scale_factor) in enumerate(self.scale_factors[::-1]):
            res[0], res[1] = res[0] * 1 / scale_factor[0], res[1] * 1 / scale_factor[1]
            
        return res 
    
    # Temp method before integrating in orientation 
    def backward_temp(self, dist):
        """
        Run through from the base frame to the next frame, assuming the 0th frame 
        is the base and the last frame is derived
        
        
        """
        v = float(dist)

        for (i, scale_factor) in enumerate(self.scale_factors[::-1]):
            v = v * 1 / scale_factor[0]
            
        return v 