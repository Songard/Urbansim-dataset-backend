"""
采样策略和优化功能模块

实现自适应采样、批处理优化和早期终止等功能
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Iterator, Any, Union
import logging
from pathlib import Path
from dataclasses import dataclass
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


@dataclass
class SamplingConfig:
    """采样配置"""
    detection_rate: int  # 检测采样率
    segmentation_rate: int  # 分割采样率
    batch_size_detection: int = 16  # 检测批处理大小
    batch_size_segmentation: int = 8  # 分割批处理大小
    early_termination_enabled: bool = True  # 是否启用早期终止
    max_workers: int = 2  # 最大工作线程数


@dataclass
class ProcessingStats:
    """处理统计信息"""
    total_frames: int = 0
    frames_processed: int = 0
    detection_frames: int = 0
    segmentation_frames: int = 0
    processing_time: float = 0.0
    early_terminated: bool = False
    termination_reason: Optional[str] = None


class FrameLoader:
    """帧加载器，负责从视频文件中加载帧"""
    
    def __init__(self, video_path: Union[str, Path]):
        """
        初始化帧加载器
        
        Args:
            video_path: 视频文件路径
        """
        self.video_path = Path(video_path)
        self.cap = None
        self.total_frames = 0
        self.fps = 0
        self.frame_width = 0
        self.frame_height = 0
        
        self._initialize_video()
    
    def _initialize_video(self):
        """初始化视频读取器"""
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {self.video_path}")
        
        self.cap = cv2.VideoCapture(str(self.video_path))
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video: {self.video_path}")
        
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logging.info(f"Video loaded: {self.total_frames} frames, {self.fps:.1f} FPS, "
                    f"{self.frame_width}x{self.frame_height}")
    
    def load_frame(self, frame_index: int) -> Optional[np.ndarray]:
        """
        加载指定索引的帧
        
        Args:
            frame_index: 帧索引
            
        Returns:
            帧图像，如果失败返回None
        """
        if not self.cap or frame_index >= self.total_frames:
            return None
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self.cap.read()
        
        if not ret:
            logging.warning(f"Failed to read frame {frame_index}")
            return None
        
        return frame
    
    def load_frames_batch(self, frame_indices: List[int]) -> List[Tuple[int, Optional[np.ndarray]]]:
        """
        批量加载帧
        
        Args:
            frame_indices: 帧索引列表
            
        Returns:
            (帧索引, 帧图像)的列表
        """
        results = []
        
        for frame_index in frame_indices:
            frame = self.load_frame(frame_index)
            results.append((frame_index, frame))
        
        return results
    
    def get_video_info(self) -> Dict[str, Any]:
        """获取视频信息"""
        return {
            "path": str(self.video_path),
            "total_frames": self.total_frames,
            "fps": self.fps,
            "width": self.frame_width,
            "height": self.frame_height,
            "duration_seconds": self.total_frames / self.fps if self.fps > 0 else 0
        }
    
    def close(self):
        """关闭视频读取器"""
        if self.cap:
            self.cap.release()
            self.cap = None


class AdaptiveSamplingStrategy:
    """自适应采样策略"""
    
    @staticmethod
    def calculate_optimal_rates(total_frames: int, 
                              target_detection_frames: int = 200,
                              target_segmentation_frames: int = 100) -> SamplingConfig:
        """
        计算最优采样率
        
        Args:
            total_frames: 总帧数
            target_detection_frames: 目标检测帧数
            target_segmentation_frames: 目标分割帧数
            
        Returns:
            采样配置
        """
        # 计算检测采样率
        detection_rate = max(1, total_frames // target_detection_frames)
        
        # 计算分割采样率（通常比检测稀疏）
        segmentation_rate = max(detection_rate, total_frames // target_segmentation_frames)
        
        # 根据总帧数调整批处理大小
        if total_frames <= 500:
            batch_detection = 8
            batch_segmentation = 4
        elif total_frames <= 2000:
            batch_detection = 16
            batch_segmentation = 8
        else:
            batch_detection = 32
            batch_segmentation = 16
        
        return SamplingConfig(
            detection_rate=detection_rate,
            segmentation_rate=segmentation_rate,
            batch_size_detection=batch_detection,
            batch_size_segmentation=batch_segmentation,
            early_termination_enabled=True,
            max_workers=min(4, max(1, total_frames // 1000))
        )
    
    @staticmethod
    def generate_sampling_plan(total_frames: int, config: SamplingConfig) -> Dict[str, List[int]]:
        """
        生成采样计划
        
        Args:
            total_frames: 总帧数
            config: 采样配置
            
        Returns:
            采样计划字典
        """
        # 生成检测帧索引
        detection_indices = list(range(0, total_frames, config.detection_rate))
        
        # 生成分割帧索引
        segmentation_indices = list(range(0, total_frames, config.segmentation_rate))
        
        # 确保分割帧是检测帧的子集（或重叠）
        detection_set = set(detection_indices)
        segmentation_indices = [idx for idx in segmentation_indices if idx in detection_set]
        
        return {
            "detection_frames": detection_indices,
            "segmentation_frames": segmentation_indices,
            "detection_batches": AdaptiveSamplingStrategy._create_batches(
                detection_indices, config.batch_size_detection
            ),
            "segmentation_batches": AdaptiveSamplingStrategy._create_batches(
                segmentation_indices, config.batch_size_segmentation
            )
        }
    
    @staticmethod
    def _create_batches(indices: List[int], batch_size: int) -> List[List[int]]:
        """将索引列表分割成批次"""
        batches = []
        for i in range(0, len(indices), batch_size):
            batches.append(indices[i:i + batch_size])
        return batches


class ProcessingOptimizer:
    """处理优化器"""
    
    def __init__(self, config: SamplingConfig):
        """
        初始化处理优化器
        
        Args:
            config: 采样配置
        """
        self.config = config
        self.stats = ProcessingStats()
        self._processing_start_time = 0
        self._lock = threading.Lock()
    
    def optimize_frame_loading(self, frame_loader: FrameLoader, 
                              frame_indices: List[int]) -> List[Tuple[int, Optional[np.ndarray]]]:
        """
        优化帧加载过程
        
        Args:
            frame_loader: 帧加载器
            frame_indices: 要加载的帧索引列表
            
        Returns:
            加载的帧数据列表
        """
        # 按索引排序以优化磁盘读取
        sorted_indices = sorted(frame_indices)
        
        # 批量加载
        results = frame_loader.load_frames_batch(sorted_indices)
        
        # 恢复原始顺序（如果需要）
        if sorted_indices != frame_indices:
            index_map = {idx: (idx, frame) for idx, frame in results}
            results = [index_map[idx] for idx in frame_indices if idx in index_map]
        
        return results
    
    def parallel_batch_processing(self, processing_func, 
                                batches: List[List], 
                                max_workers: Optional[int] = None) -> List[Any]:
        """
        并行批处理
        
        Args:
            processing_func: 处理函数
            batches: 批次列表
            max_workers: 最大工作线程数
            
        Returns:
            处理结果列表
        """
        if max_workers is None:
            max_workers = self.config.max_workers
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有批次任务
            future_to_batch = {
                executor.submit(processing_func, batch): i 
                for i, batch in enumerate(batches)
            }
            
            # 收集结果
            batch_results = [None] * len(batches)
            
            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    result = future.result()
                    batch_results[batch_idx] = result
                except Exception as e:
                    logging.error(f"Batch {batch_idx} processing failed: {e}")
                    batch_results[batch_idx] = None
            
            # 合并批次结果
            for batch_result in batch_results:
                if batch_result is not None:
                    if isinstance(batch_result, list):
                        results.extend(batch_result)
                    else:
                        results.append(batch_result)
        
        return results
    
    def memory_efficient_processing(self, 
                                  processing_iterator: Iterator,
                                  progress_callback: Optional[callable] = None) -> Iterator:
        """
        内存高效的处理迭代器
        
        Args:
            processing_iterator: 处理迭代器
            progress_callback: 进度回调函数
            
        Yields:
            处理结果
        """
        processed_count = 0
        
        for item in processing_iterator:
            yield item
            processed_count += 1
            
            # 更新统计
            with self._lock:
                self.stats.frames_processed = processed_count
            
            # 调用进度回调
            if progress_callback:
                progress_callback(processed_count, self.stats)
    
    def start_timing(self):
        """开始计时"""
        self._processing_start_time = time.time()
    
    def stop_timing(self):
        """停止计时"""
        if self._processing_start_time > 0:
            self.stats.processing_time = time.time() - self._processing_start_time
    
    def update_stats(self, **kwargs):
        """更新统计信息"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.stats, key):
                    setattr(self.stats, key, value)
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """获取性能指标"""
        if self.stats.processing_time <= 0:
            return {"fps": 0.0, "frames_per_second": 0.0}
        
        fps = self.stats.frames_processed / self.stats.processing_time
        
        return {
            "processing_fps": fps,
            "detection_fps": self.stats.detection_frames / self.stats.processing_time,
            "segmentation_fps": self.stats.segmentation_frames / self.stats.processing_time,
            "total_processing_time": self.stats.processing_time,
            "avg_time_per_frame": self.stats.processing_time / max(1, self.stats.frames_processed)
        }


class EarlyTerminationManager:
    """早期终止管理器"""
    
    def __init__(self, min_processed_ratio: float = 0.2):
        """
        初始化早期终止管理器
        
        Args:
            min_processed_ratio: 最小处理比例（达到此比例后才考虑早期终止）
        """
        self.min_processed_ratio = min_processed_ratio
        self.termination_thresholds = {
            "WDD": 12.0,
            "WPO": 40.0,
            "SAI": 35.0
        }
    
    def should_terminate(self, current_metrics: Dict[str, float], 
                        processed_ratio: float) -> Tuple[bool, Optional[str]]:
        """
        判断是否应该早期终止
        
        Args:
            current_metrics: 当前指标值
            processed_ratio: 已处理比例
            
        Returns:
            (是否终止, 终止原因)
        """
        if processed_ratio < self.min_processed_ratio:
            return False, None
        
        violations = []
        
        for metric, threshold in self.termination_thresholds.items():
            value = current_metrics.get(metric, 0.0)
            if value > threshold:
                violations.append(f"{metric}={value:.1f}>{threshold}")
        
        if violations:
            reason = f"Early termination at {processed_ratio:.1%}: {', '.join(violations)}"
            return True, reason
        
        return False, None
    
    def update_thresholds(self, new_thresholds: Dict[str, float]):
        """更新终止阈值"""
        self.termination_thresholds.update(new_thresholds)


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self, memory_limit_mb: float = 2048):
        """
        初始化资源监控器
        
        Args:
            memory_limit_mb: 内存限制（MB）
        """
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.peak_memory_usage = 0
    
    def check_memory_usage(self) -> Dict[str, float]:
        """
        检查当前内存使用情况
        
        Returns:
            内存使用信息
        """
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            current_memory = memory_info.rss  # 物理内存使用量
            self.peak_memory_usage = max(self.peak_memory_usage, current_memory)
            
            return {
                "current_mb": current_memory / 1024 / 1024,
                "peak_mb": self.peak_memory_usage / 1024 / 1024,
                "limit_mb": self.memory_limit_bytes / 1024 / 1024,
                "usage_ratio": current_memory / self.memory_limit_bytes
            }
        except ImportError:
            logging.warning("psutil not available for memory monitoring")
            return {"current_mb": 0, "peak_mb": 0, "limit_mb": 0, "usage_ratio": 0}
    
    def is_memory_limit_exceeded(self) -> bool:
        """检查是否超出内存限制"""
        memory_info = self.check_memory_usage()
        return memory_info["usage_ratio"] > 0.9  # 90%阈值