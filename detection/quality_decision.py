"""
综合判定和输出模块 (Quality Decision and Output Module)

Implements quality decision logic based on three core metrics for 3D reconstruction assessment:

Quality Decision Logic:
1. REJECT: Any single metric exceeds critical threshold (immediate failure)
   - WDD > 8.0: Too many moving objects detected
   - WPO > 5%: Too much scene coverage by objects  
   - SAI > 15%: Excessive photographer self-appearance

2. NEED_REVIEW: Two or more metrics exceed problem thresholds (manual review needed)
   - WDD > 1.0: Moderate moving object activity
   - WPO > 1%: Noticeable scene coverage
   - SAI > 3%: Some self-appearance detected

3. PASS: All metrics below problem thresholds (suitable for 3D reconstruction)

4. ERROR: Technical issues during detection process

Metric Quality Levels:
- Excellent: Minimal interference (WDD<0.2, WPO<0.1%, SAI<0.5%)
- Acceptable: Minor issues (WDD<0.8, WPO<0.5%, SAI<2%)  
- Review: Noticeable problems (WDD<2.0, WPO<1.5%, SAI<5%)
- Reject: Critical issues (exceeds review thresholds)

Scene-specific thresholds supported (indoor/outdoor/default) with different tolerance levels.
"""

import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from enum import Enum

from .metrics_calculator import FinalMetrics, ThresholdManager


class QualityDecision(Enum):
    """质量判定结果枚举"""
    PASS = "PASS"
    NEED_REVIEW = "NEED_REVIEW"
    REJECT = "REJECT"
    ERROR = "ERROR"


class MetricLevel(Enum):
    """指标等级枚举"""
    EXCELLENT = "excellent"
    ACCEPTABLE = "acceptable" 
    REVIEW = "review"
    REJECT = "reject"


@dataclass
class MetricEvaluation:
    """单个指标评估结果"""
    value: float
    level: MetricLevel
    threshold_info: Dict[str, float]
    is_problematic: bool


@dataclass
class QualityAssessmentResult:
    """质量评估完整结果"""
    # 基础指标
    metrics: Dict[str, float]  # WDD, WPO, SAI值
    decision: QualityDecision
    
    # 详细评估
    metric_evaluations: Dict[str, MetricEvaluation]
    problems_found: List[str]
    
    # 处理信息
    processing_details: Dict[str, Any]
    
    # 时间戳和配置
    timestamp: str
    scene_type: str
    
    # 统计信息
    statistics: Optional[Dict[str, Any]] = None


class QualityDecisionEngine:
    """质量判定引擎"""
    
    # These will be replaced by config-based values
    REJECT_THRESHOLDS = None
    PROBLEM_THRESHOLDS = None
    
    def __init__(self, scene_type: str = "default"):
        """
        初始化质量判定引擎
        
        Args:
            scene_type: 场景类型
        """
        from config import Config
        self.scene_type = scene_type
        self.threshold_manager = ThresholdManager(scene_type)
        
        # Initialize thresholds from config
        self.REJECT_THRESHOLDS = Config.get_reject_thresholds()
        self.PROBLEM_THRESHOLDS = Config.get_problem_thresholds()
    
    def evaluate_quality(self, metrics: FinalMetrics, 
                        processing_stats: Optional[Dict] = None,
                        additional_stats: Optional[Dict] = None) -> QualityAssessmentResult:
        """
        执行质量评估
        
        Args:
            metrics: 最终指标
            processing_stats: 处理统计信息
            additional_stats: 额外统计信息
            
        Returns:
            质量评估结果
        """
        # 提取指标值
        metric_values = {
            "WDD": metrics.WDD,
            "WPO": metrics.WPO,
            "SAI": metrics.SAI
        }
        
        # 评估各个指标
        metric_evaluations = {}
        for metric_name, value in metric_values.items():
            evaluation = self._evaluate_single_metric(metric_name, value)
            metric_evaluations[metric_name] = evaluation
        
        # 执行综合判定
        decision, problems = self._make_decision(metric_evaluations)
        
        # 整理处理详情
        processing_details = {
            "frames_sampled": metrics.frames_sampled,
            "frames_total": metrics.frames_total,
            "sampling_rates": metrics.sampling_rates
        }
        
        if processing_stats:
            processing_details.update(processing_stats)
        
        # 创建评估结果
        result = QualityAssessmentResult(
            metrics=metric_values,
            decision=decision,
            metric_evaluations=metric_evaluations,
            problems_found=problems,
            processing_details=processing_details,
            timestamp=datetime.now().isoformat(),
            scene_type=self.scene_type,
            statistics=additional_stats
        )
        
        return result
    
    def _evaluate_single_metric(self, metric_name: str, value: float) -> MetricEvaluation:
        """
        评估单个指标
        
        Args:
            metric_name: 指标名称
            value: 指标值
            
        Returns:
            指标评估结果
        """
        # 获取阈值信息
        thresholds = self.threshold_manager.thresholds.get(metric_name, {})
        
        # 评估等级
        level_str = self.threshold_manager.evaluate_metric(metric_name, value)
        level = MetricLevel(level_str)
        
        # 判断是否有问题
        problem_threshold = self.PROBLEM_THRESHOLDS.get(metric_name, float('inf'))
        is_problematic = value >= problem_threshold
        
        return MetricEvaluation(
            value=value,
            level=level,
            threshold_info=thresholds,
            is_problematic=is_problematic
        )
    
    def _make_decision(self, metric_evaluations: Dict[str, MetricEvaluation]) -> Tuple[QualityDecision, List[str]]:
        """
        执行综合判定
        
        Args:
            metric_evaluations: 指标评估结果
            
        Returns:
            (判定结果, 问题列表)
        """
        problems = []
        
        # 检查单指标否决
        for metric_name, evaluation in metric_evaluations.items():
            reject_threshold = self.REJECT_THRESHOLDS.get(metric_name, float('inf'))
            
            if evaluation.value >= reject_threshold:
                problems.append(f"{metric_name} 严重超标: {evaluation.value:.2f} >= {reject_threshold}")
                return QualityDecision.REJECT, problems
        
        # 统计问题指标数量
        problem_count = sum(1 for eval in metric_evaluations.values() if eval.is_problematic)
        
        # 收集问题详情
        for metric_name, evaluation in metric_evaluations.items():
            if evaluation.is_problematic:
                problem_threshold = self.PROBLEM_THRESHOLDS.get(metric_name, 0)
                problems.append(f"{metric_name} 需关注: {evaluation.value:.2f} >= {problem_threshold}")
        
        # 两个或以上指标有问题，需要复核
        if problem_count >= 2:
            return QualityDecision.NEED_REVIEW, problems
        
        # 检查是否有review级别的指标
        review_count = sum(1 for eval in metric_evaluations.values() if eval.level == MetricLevel.REVIEW)
        if review_count > 0:
            return QualityDecision.NEED_REVIEW, problems
        
        # 否则通过
        return QualityDecision.PASS, problems
    
    def get_decision_summary(self, result: QualityAssessmentResult) -> str:
        """
        获取判定结果摘要
        
        Args:
            result: 质量评估结果
            
        Returns:
            摘要文本
        """
        decision_texts = {
            QualityDecision.PASS: "通过",
            QualityDecision.NEED_REVIEW: "需要复核",
            QualityDecision.REJECT: "拒绝",
            QualityDecision.ERROR: "错误"
        }
        
        decision_text = decision_texts.get(result.decision, "未知")
        
        summary_parts = [f"判定结果: {decision_text}"]
        
        # 添加指标摘要
        metrics_summary = []
        for metric_name, value in result.metrics.items():
            evaluation = result.metric_evaluations.get(metric_name)
            level_text = evaluation.level.value if evaluation else "unknown"
            metrics_summary.append(f"{metric_name}={value:.2f}({level_text})")
        
        summary_parts.append(f"指标: {', '.join(metrics_summary)}")
        
        # 添加问题摘要
        if result.problems_found:
            summary_parts.append(f"问题: {len(result.problems_found)}项")
        
        return " | ".join(summary_parts)


class ResultFormatter:
    """结果格式化器"""
    
    @staticmethod
    def to_json(result: QualityAssessmentResult, indent: Optional[int] = 2) -> str:
        """
        将结果转换为JSON格式
        
        Args:
            result: 质量评估结果
            indent: JSON缩进
            
        Returns:
            JSON字符串
        """
        # 转换为可序列化的字典
        result_dict = ResultFormatter._to_serializable_dict(result)
        
        return json.dumps(result_dict, indent=indent, ensure_ascii=False)
    
    @staticmethod
    def to_compact_json(result: QualityAssessmentResult) -> str:
        """
        将结果转换为紧凑JSON格式
        
        Args:
            result: 质量评估结果
            
        Returns:
            紧凑JSON字符串
        """
        # 只包含关键信息的紧凑格式
        compact_result = {
            "metrics": {
                "WDD": round(result.metrics["WDD"], 2),
                "WPO": round(result.metrics["WPO"], 1),
                "SAI": round(result.metrics["SAI"], 1)
            },
            "decision": result.decision.value,
            "details": {
                "frames_sampled": result.processing_details.get("frames_sampled", 0),
                "frames_total": result.processing_details.get("frames_total", 0),
                "sampling_rate": result.processing_details.get("sampling_rates", {})
            },
            "timestamp": result.timestamp
        }
        
        return json.dumps(compact_result, separators=(',', ':'), ensure_ascii=False)
    
    @staticmethod
    def to_table_format(result: QualityAssessmentResult) -> str:
        """
        将结果转换为表格格式
        
        Args:
            result: 质量评估结果
            
        Returns:
            表格格式字符串
        """
        lines = []
        lines.append("=" * 60)
        lines.append("移动障碍物检测质量评估结果")
        lines.append("=" * 60)
        
        # 基本信息
        lines.append(f"时间: {result.timestamp}")
        lines.append(f"场景类型: {result.scene_type}")
        lines.append(f"判定结果: {result.decision.value}")
        lines.append("")
        
        # 指标详情
        lines.append("指标详情:")
        lines.append("-" * 40)
        for metric_name, value in result.metrics.items():
            evaluation = result.metric_evaluations.get(metric_name)
            if evaluation:
                level = evaluation.level.value
                lines.append(f"  {metric_name:3s}: {value:8.2f} ({level})")
            else:
                lines.append(f"  {metric_name:3s}: {value:8.2f}")
        lines.append("")
        
        # 处理信息
        details = result.processing_details
        lines.append("处理信息:")
        lines.append("-" * 40)
        lines.append(f"  总帧数: {details.get('frames_total', 0):,}")
        lines.append(f"  采样帧数: {details.get('frames_sampled', 0):,}")
        
        sampling_rates = details.get('sampling_rates', {})
        if sampling_rates:
            lines.append(f"  检测采样率: 1/{sampling_rates.get('detection', 1)}")
            lines.append(f"  分割采样率: 1/{sampling_rates.get('segmentation', 1)}")
        
        # 问题列表
        if result.problems_found:
            lines.append("")
            lines.append("发现问题:")
            lines.append("-" * 40)
            for i, problem in enumerate(result.problems_found, 1):
                lines.append(f"  {i}. {problem}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    @staticmethod
    def _to_serializable_dict(result: QualityAssessmentResult) -> Dict:
        """将结果转换为可序列化的字典"""
        result_dict = asdict(result)
        
        # 转换枚举值
        result_dict["decision"] = result.decision.value
        
        # 转换指标评估
        metric_evals = {}
        for metric_name, evaluation in result.metric_evaluations.items():
            metric_evals[metric_name] = {
                "value": evaluation.value,
                "level": evaluation.level.value,
                "threshold_info": evaluation.threshold_info,
                "is_problematic": evaluation.is_problematic
            }
        result_dict["metric_evaluations"] = metric_evals
        
        return result_dict


class QualityReportGenerator:
    """质量报告生成器"""
    
    def __init__(self, output_format: str = "json"):
        """
        初始化报告生成器
        
        Args:
            output_format: 输出格式 ("json", "compact", "table")
        """
        self.output_format = output_format
        self.formatter = ResultFormatter()
    
    def generate_report(self, result: QualityAssessmentResult) -> str:
        """
        生成质量报告
        
        Args:
            result: 质量评估结果
            
        Returns:
            报告内容
        """
        if self.output_format == "json":
            return self.formatter.to_json(result)
        elif self.output_format == "compact":
            return self.formatter.to_compact_json(result)
        elif self.output_format == "table":
            return self.formatter.to_table_format(result)
        else:
            raise ValueError(f"Unsupported output format: {self.output_format}")
    
    def save_report(self, result: QualityAssessmentResult, 
                   output_path: str, encoding: str = "utf-8") -> bool:
        """
        保存质量报告到文件
        
        Args:
            result: 质量评估结果
            output_path: 输出文件路径
            encoding: 文件编码
            
        Returns:
            是否保存成功
        """
        try:
            report_content = self.generate_report(result)
            
            with open(output_path, 'w', encoding=encoding) as f:
                f.write(report_content)
            
            logging.info(f"Quality report saved to: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to save report: {e}")
            return False
    
    def generate_batch_summary(self, results: List[QualityAssessmentResult]) -> str:
        """
        生成批量处理摘要
        
        Args:
            results: 质量评估结果列表
            
        Returns:
            批量摘要
        """
        if not results:
            return "无结果数据"
        
        # 统计各种判定结果
        decision_counts = {}
        for result in results:
            decision = result.decision.value
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        
        # 计算指标统计
        metric_stats = {}
        for metric_name in ["WDD", "WPO", "SAI"]:
            values = [r.metrics[metric_name] for r in results if metric_name in r.metrics]
            if values:
                metric_stats[metric_name] = {
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }
        
        # 生成摘要
        lines = []
        lines.append(f"批量处理摘要 (共{len(results)}个结果)")
        lines.append("=" * 50)
        
        # 判定结果统计
        lines.append("判定结果分布:")
        for decision, count in decision_counts.items():
            percentage = (count / len(results)) * 100
            lines.append(f"  {decision}: {count} ({percentage:.1f}%)")
        
        # 指标统计
        lines.append("\n指标统计:")
        for metric_name, stats in metric_stats.items():
            lines.append(f"  {metric_name}: 均值={stats['mean']:.2f}, "
                        f"范围=[{stats['min']:.2f}, {stats['max']:.2f}]")
        
        return "\n".join(lines)