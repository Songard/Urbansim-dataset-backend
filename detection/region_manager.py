"""
区域定义和权重计算模块

实现图像区域划分、权重分配和坐标计算功能
"""

import math
from typing import Dict, List, Tuple, Any


class RegionManager:
    """图像区域管理器，负责区域划分和权重计算"""
    
    def __init__(self, img_width: int, img_height: int):
        """
        初始化区域管理器
        
        Args:
            img_width: 图像宽度
            img_height: 图像高度
        """
        self.img_width = img_width
        self.img_height = img_height
        self.center_x = img_width / 2
        self.center_y = img_height / 2
        self.ref_length = min(img_width, img_height)
        
        self.regions = self._define_regions()
    
    def _define_regions(self) -> Dict[str, Any]:
        """
        定义区域范围和权重
        
        Returns:
            区域配置字典
        """
        return {
            "core": {
                "type": "circle",
                "radius": self.ref_length * 0.6,
                "weight": 3.0,
                "center": (self.center_x, self.center_y)
            },
            "middle": {
                "type": "ring",
                "inner_radius": self.ref_length * 0.6,
                "outer_radius": self.ref_length * 0.85,
                "weight": 1.5,
                "center": (self.center_x, self.center_y)
            },
            "edge": {
                "type": "ring",
                "inner_radius": self.ref_length * 0.85,
                "outer_radius": float('inf'),
                "weight": 0.5,
                "center": (self.center_x, self.center_y)
            },
            "self_zone": {
                "type": "areas",
                "areas": [
                    {
                        "x": [0, self.img_width * 0.5],
                        "y": [self.img_height * 0.7, self.img_height]
                    },
                    {
                        "x": [self.img_width * 0.5, self.img_width],
                        "y": [self.img_height * 0.7, self.img_height]
                    }
                ],
                "weight": -1
            }
        }
    
    def get_point_region(self, x: float, y: float) -> str:
        """
        获取点所在的区域
        
        Args:
            x: 点的x坐标
            y: 点的y坐标
            
        Returns:
            区域名称
        """
        if self._is_in_self_zone(x, y):
            return "self_zone"
        
        distance = math.sqrt((x - self.center_x)**2 + (y - self.center_y)**2)
        
        if distance <= self.regions["core"]["radius"]:
            return "core"
        elif distance <= self.regions["middle"]["outer_radius"]:
            return "middle"
        else:
            return "edge"
    
    def get_bbox_region_weights(self, bbox: Tuple[float, float, float, float]) -> Dict[str, float]:
        """
        计算边界框在各区域的权重分布
        
        Args:
            bbox: 边界框 (x1, y1, x2, y2)
            
        Returns:
            各区域权重字典
        """
        x1, y1, x2, y2 = bbox
        
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        primary_region = self.get_point_region(center_x, center_y)
        
        return {primary_region: 1.0}
    
    def get_mask_region_weights(self, mask_points: List[Tuple[float, float]]) -> Dict[str, float]:
        """
        计算分割掩码在各区域的权重分布
        
        Args:
            mask_points: 分割掩码点集合
            
        Returns:
            各区域权重字典
        """
        if not mask_points:
            return {}
        
        region_counts = {"core": 0, "middle": 0, "edge": 0, "self_zone": 0}
        
        for x, y in mask_points:
            region = self.get_point_region(x, y)
            region_counts[region] += 1
        
        total_points = len(mask_points)
        region_ratios = {k: v / total_points for k, v in region_counts.items()}
        
        return region_ratios
    
    def get_region_weight(self, region_name: str) -> float:
        """
        获取区域权重
        
        Args:
            region_name: 区域名称
            
        Returns:
            区域权重值
        """
        return self.regions.get(region_name, {}).get("weight", 0.0)
    
    def calculate_weighted_value(self, region_weights: Dict[str, float], base_value: float = 1.0) -> float:
        """
        计算加权值
        
        Args:
            region_weights: 各区域权重分布
            base_value: 基础值
            
        Returns:
            加权后的值
        """
        weighted_sum = 0.0
        for region, ratio in region_weights.items():
            region_weight = self.get_region_weight(region)
            weighted_sum += base_value * ratio * region_weight
        
        return weighted_sum
    
    def _is_in_self_zone(self, x: float, y: float) -> bool:
        """
        检查点是否在自身入镜区域
        
        Args:
            x: 点的x坐标
            y: 点的y坐标
            
        Returns:
            是否在自身入镜区域
        """
        for area in self.regions["self_zone"]["areas"]:
            x_range = area["x"]
            y_range = area["y"]
            
            if x_range[0] <= x <= x_range[1] and y_range[0] <= y <= y_range[1]:
                return True
        
        return False
    
    def is_large_detection_in_self_zone(self, bbox: Tuple[float, float, float, float], 
                                       area_threshold: float = 0.02) -> bool:
        """
        检查是否是在自身入镜区域的大型检测（降低阈值提高敏感度）
        
        Args:
            bbox: 边界框 (x1, y1, x2, y2)
            area_threshold: 面积阈值（占画面比例，降低到2%）
            
        Returns:
            是否符合自身入镜条件
        """
        x1, y1, x2, y2 = bbox
        
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        if not self._is_in_self_zone(center_x, center_y):
            return False
        
        bbox_area = (x2 - x1) * (y2 - y1)
        image_area = self.img_width * self.img_height
        area_ratio = bbox_area / image_area
        
        return area_ratio > area_threshold
    
    def calculate_self_appearance_score(self, bbox: Tuple[float, float, float, float]) -> float:
        """
        计算自身入镜得分（更细粒度的SAI计算）
        
        Args:
            bbox: 边界框 (x1, y1, x2, y2)
            
        Returns:
            自身入镜得分 (0.0-1.0)
        """
        x1, y1, x2, y2 = bbox
        
        # 计算检测框的基本属性
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        bbox_area = (x2 - x1) * (y2 - y1)
        image_area = self.img_width * self.img_height
        area_ratio = bbox_area / image_area
        
        # 初始得分
        score = 0.0
        
        # 1. 位置得分：在画面下方得分更高
        y_ratio = center_y / self.img_height
        if y_ratio > 0.6:  # 下方60%区域
            position_score = (y_ratio - 0.6) / 0.4  # 0.6-1.0映射到0-1
            score += position_score * 0.4  # 位置权重40%
        
        # 2. 大小得分：适中大小得分更高
        if area_ratio > 0.01:  # 至少1%画面
            if area_ratio <= 0.15:  # 1%-15%为合理范围
                size_score = min(area_ratio / 0.05, 1.0)  # 5%时达到满分
            else:  # 超过15%开始降分
                size_score = max(0.5, 1.0 - (area_ratio - 0.15) / 0.35)
            score += size_score * 0.3  # 大小权重30%
        
        # 3. 中心性得分：靠近画面中央水平位置
        x_center_distance = abs(center_x - self.img_width / 2) / (self.img_width / 2)
        centrality_score = 1.0 - x_center_distance
        score += centrality_score * 0.2  # 中心性权重20%
        
        # 4. 自身区域得分：在定义的自身区域内
        if self._is_in_self_zone(center_x, center_y):
            score += 0.1  # 自身区域额外10%
        
        return min(score, 1.0)  # 确保不超过1.0
    
    def get_region_info(self) -> Dict[str, Any]:
        """
        获取区域配置信息
        
        Returns:
            区域配置信息
        """
        return {
            "image_size": (self.img_width, self.img_height),
            "center": (self.center_x, self.center_y),
            "reference_length": self.ref_length,
            "regions": self.regions
        }