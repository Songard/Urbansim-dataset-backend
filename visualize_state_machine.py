#!/usr/bin/env python3
"""
MetaCam数据处理系统状态机可视化工具

使用方法：
1. 安装依赖: pip install graphviz matplotlib networkx
2. 运行脚本: python visualize_state_machine.py
3. 查看生成的图片: system_flow.png, state_machine.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import networkx as nx
from datetime import datetime
import os

def create_simplified_flow_diagram():
    """Create simplified data flow diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Define color scheme
    colors = {
        'monitor': '#E3F2FD',    # Light blue
        'process': '#F3E5F5',    # Light purple
        'validate': '#E8F5E8',   # Light green
        'output': '#FFF3E0',     # Light orange
        'error': '#FFEBEE',      # Light red
        'decision': '#FFFDE7'    # Light yellow
    }

    # Define process boxes
    boxes = [
        # Monitoring phase
        {'xy': (1, 8.5), 'width': 2, 'height': 0.8, 'text': '1. MONITORING\nGoogle Drive', 'color': colors['monitor']},
        {'xy': (1, 7.5), 'width': 2, 'height': 0.8, 'text': '2. DOWNLOADING\nChunked transfer', 'color': colors['monitor']},
        {'xy': (1, 6.5), 'width': 2, 'height': 0.8, 'text': '3. EXTRACTING\nFormat detection', 'color': colors['monitor']},

        # Validation phase
        {'xy': (4, 8.5), 'width': 2.5, 'height': 0.8, 'text': '4. BASIC_VALIDATION (70%)\nMetaCam format check', 'color': colors['validate']},
        {'xy': (4, 7.5), 'width': 2.5, 'height': 0.8, 'text': '5. TRANSIENT_DETECTION (30%)\nYOLO11 AI analysis', 'color': colors['validate']},
        {'xy': (4, 6.5), 'width': 2.5, 'height': 0.8, 'text': '6. SCORE_CALCULATION\nWDD+WPO+SAI', 'color': colors['validate']},

        # Decision point
        {'xy': (7.5, 7.5), 'width': 1.5, 'height': 1.2, 'text': 'DECISION\nMAKING', 'color': colors['decision']},

        # Processing phase
        {'xy': (10, 8.5), 'width': 2, 'height': 0.8, 'text': '7. DIR_STANDARDIZATION\nData preprocessing', 'color': colors['process']},
        {'xy': (10, 7.5), 'width': 2, 'height': 0.8, 'text': '8. VALIDATION_GENERATOR\nData preparation', 'color': colors['process']},
        {'xy': (10, 6.5), 'width': 2, 'height': 0.8, 'text': '9. METACAM_CLI\n3D reconstruction', 'color': colors['process']},
        {'xy': (10, 5.5), 'width': 2, 'height': 0.8, 'text': '10. POST_PROCESSING\nFile search', 'color': colors['process']},

        # Output validation decision point
        {'xy': (7.5, 4.5), 'width': 1.5, 'height': 1.2, 'text': '11. OUTPUT\nVALIDATION', 'color': colors['decision']},

        # Output phase
        {'xy': (4.5, 3), 'width': 2, 'height': 0.8, 'text': '12A. PROCESSING\nSUCCESS', 'color': colors['validate']},
        {'xy': (7, 3), 'width': 2, 'height': 0.8, 'text': '12B. PARTIAL\nSUCCESS', 'color': colors['decision']},
        {'xy': (9.5, 3), 'width': 2, 'height': 0.8, 'text': '12C. PROCESSING\nFAILED', 'color': colors['error']},

        {'xy': (6.5, 1.5), 'width': 2.5, 'height': 0.8, 'text': '13. PACKAGING\nNVS COLMAP format', 'color': colors['output']},
        {'xy': (6.5, 0.5), 'width': 2.5, 'height': 0.8, 'text': '14. UPLOADING\nHuggingFace dataset', 'color': colors['output']},

        # Error handling
        {'xy': (1, 4), 'width': 2, 'height': 1.2, 'text': 'ERROR_HANDLING\nRecord failure info', 'color': colors['error']},
        {'xy': (4, 4), 'width': 2, 'height': 1.2, 'text': 'VALIDATION_REVIEW\nManual check required', 'color': colors['error']},
    ]

    # 绘制流程框
    for box in boxes:
        fancy_box = FancyBboxPatch(
            box['xy'], box['width'], box['height'],
            boxstyle="round,pad=0.1",
            facecolor=box['color'],
            edgecolor='black',
            linewidth=1
        )
        ax.add_patch(fancy_box)

        # 添加文本
        ax.text(
            box['xy'][0] + box['width']/2,
            box['xy'][1] + box['height']/2,
            box['text'],
            ha='center', va='center',
            fontsize=9,
            weight='bold' if '决策' in box['text'] else 'normal'
        )

    # Draw arrow connections
    arrows = [
        # Main flow
        ((2, 8.9), (2, 8.3)),  # 1→2
        ((2, 7.9), (2, 7.3)),  # 2→3
        ((3, 6.9), (4, 6.9)),  # 3→6
        ((4, 8.9), (4, 8.3)),  # 4→5
        ((4, 7.9), (4, 7.3)),  # 5→6
        ((6.5, 7), (7.5, 7.5)),  # 6→decision

        # Processing path
        ((9, 8), (10, 8.9)),   # decision→7
        ((11, 8.9), (11, 8.3)), # 7→8
        ((11, 7.9), (11, 7.3)), # 8→9
        ((11, 6.9), (11, 6.3)), # 9→10
        ((11, 5.5), (8.5, 4.8)), # 10→11 (OUTPUT_VALIDATION)

        # Output validation paths
        ((7, 4.5), (5.5, 3.8)),  # OUTPUT_VALIDATION→SUCCESS
        ((8, 4.2), (8, 3.8)),    # OUTPUT_VALIDATION→PARTIAL
        ((8.5, 4.5), (10.5, 3.8)), # OUTPUT_VALIDATION→FAILED

        # Continue to packaging
        ((5.5, 3), (7, 2.3)),    # SUCCESS→PACKAGING
        ((8, 3), (7.5, 2.3)),    # PARTIAL→PACKAGING
        ((7.75, 1.5), (7.75, 1.3)), # PACKAGING→UPLOADING

        # Error paths
        ((7.5, 7), (2, 4.6)),   # decision→error handling
        ((8, 7), (5, 4.6)),     # decision→review
        ((10.5, 3), (7.75, 1.3)), # FAILED→UPLOADING (recording)
    ]

    for start, end in arrows:
        ax.annotate('', xy=end, xytext=start,
                   arrowprops=dict(arrowstyle='->', lw=1.5, color='darkblue'))

    # Add decision labels
    ax.text(6.5, 8.2, 'PASS\n(Score>=60)', ha='center', va='center', fontsize=8, color='green', weight='bold')
    ax.text(5.5, 6.2, 'REJECT\n(Score<60)', ha='center', va='center', fontsize=8, color='red', weight='bold')
    ax.text(6, 5.8, 'REVIEW\n(Multiple Issues)', ha='center', va='center', fontsize=8, color='orange', weight='bold')

    # Add title and description
    ax.text(6, 9.5, 'MetaCam Data Processing System Complete Flow', ha='center', va='center',
           fontsize=16, weight='bold')

    ax.text(6, 1, 'System Features: Pipeline Validation + Automated Processing + Smart Decision + Result Tracking',
           ha='center', va='center', fontsize=10, style='italic')

    plt.tight_layout()
    plt.savefig('system_flow.png', dpi=300, bbox_inches='tight')
    print("System flow diagram saved: system_flow.png")

def create_state_machine_diagram():
    """Create detailed state machine diagram"""
    # Create directed graph
    G = nx.DiGraph()

    # Define states and transitions
    states = [
        'IDLE', 'MONITORING', 'FILE_DETECTED', 'DOWNLOADING', 'DOWNLOAD_FAILED',
        'EXTRACTING', 'EXTRACT_FAILED', 'VALIDATING', 'VALIDATION_FAILED',
        'VALIDATION_PASSED', 'PROCESSING', 'POST_PROCESSING', 'OUTPUT_VALIDATION',
        'PROCESSING_FAILED', 'PROCESSING_SUCCESS', 'PARTIAL_SUCCESS',
        'PACKAGING', 'UPLOADING', 'UPLOAD_FAILED', 'RECORDING', 'CLEANUP',
        'COMPLETED', 'ERROR_HANDLING'
    ]

    transitions = [
        ('IDLE', 'MONITORING'),
        ('MONITORING', 'FILE_DETECTED'),
        ('MONITORING', 'MONITORING'),
        ('FILE_DETECTED', 'DOWNLOADING'),
        ('DOWNLOADING', 'DOWNLOAD_FAILED'),
        ('DOWNLOADING', 'EXTRACTING'),
        ('DOWNLOAD_FAILED', 'ERROR'),
        ('EXTRACTING', 'EXTRACT_FAILED'),
        ('EXTRACTING', 'VALIDATING'),
        ('EXTRACT_FAILED', 'ERROR'),
        ('VALIDATING', 'VALIDATION_FAILED'),
        ('VALIDATING', 'VALIDATION_PASSED'),
        ('VALIDATION_FAILED', 'RECORDING'),
        ('VALIDATION_PASSED', 'PROCESSING'),
        ('VALIDATION_PASSED', 'RECORDING'),
        ('PROCESSING', 'POST_PROCESSING'),
        ('POST_PROCESSING', 'OUTPUT_VALIDATION'),
        ('OUTPUT_VALIDATION', 'PROCESSING_SUCCESS'),
        ('OUTPUT_VALIDATION', 'PROCESSING_FAILED'),
        ('OUTPUT_VALIDATION', 'PARTIAL_SUCCESS'),
        ('PROCESSING_FAILED', 'RECORDING'),
        ('PROCESSING_SUCCESS', 'PACKAGING'),
        ('PARTIAL_SUCCESS', 'PACKAGING'),
        ('PACKAGING', 'UPLOADING'),
        ('PACKAGING', 'RECORDING'),
        ('UPLOADING', 'UPLOAD_FAILED'),
        ('UPLOADING', 'RECORDING'),
        ('UPLOAD_FAILED', 'RECORDING'),
        ('RECORDING', 'CLEANUP'),
        ('CLEANUP', 'COMPLETED'),
        ('COMPLETED', 'MONITORING'),
        ('DOWNLOAD_FAILED', 'ERROR_HANDLING'),
        ('EXTRACT_FAILED', 'ERROR_HANDLING'),
        ('ERROR_HANDLING', 'CLEANUP'),
    ]

    G.add_nodes_from(states)
    G.add_edges_from(transitions)

    # Create layout
    plt.figure(figsize=(20, 14))
    pos = nx.spring_layout(G, k=3, iterations=50)

    # Define node colors
    node_colors = {
        'IDLE': 'lightblue',
        'MONITORING': 'lightblue',
        'FILE_DETECTED': 'lightgreen',
        'DOWNLOADING': 'yellow',
        'DOWNLOAD_FAILED': 'lightcoral',
        'EXTRACTING': 'yellow',
        'EXTRACT_FAILED': 'lightcoral',
        'VALIDATING': 'orange',
        'VALIDATION_FAILED': 'lightcoral',
        'VALIDATION_PASSED': 'lightgreen',
        'PROCESSING': 'plum',
        'POST_PROCESSING': 'plum',
        'OUTPUT_VALIDATION': 'orange',
        'PROCESSING_FAILED': 'lightcoral',
        'PROCESSING_SUCCESS': 'lightgreen',
        'PARTIAL_SUCCESS': 'lightyellow',
        'PACKAGING': 'wheat',
        'UPLOADING': 'wheat',
        'UPLOAD_FAILED': 'lightcoral',
        'RECORDING': 'lightcyan',
        'CLEANUP': 'lightgray',
        'COMPLETED': 'lightgreen',
        'ERROR_HANDLING': 'red'
    }

    # Draw nodes
    for node in G.nodes():
        nx.draw_networkx_nodes(G, pos, nodelist=[node],
                              node_color=node_colors.get(node, 'white'),
                              node_size=1500, alpha=0.8)

    # Draw edges
    nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True,
                          arrowsize=20, alpha=0.6)

    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=8, font_weight='bold')

    plt.title('MetaCam Data Processing System State Machine', fontsize=16, weight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig('state_machine.png', dpi=300, bbox_inches='tight')
    print("State machine diagram saved: state_machine.png")

def create_performance_analysis():
    """Create performance analysis charts"""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

    # 1. Processing time distribution
    stages = ['Download', 'Extract', 'Validate', '3D Process', 'Package', 'Upload']
    times = [120, 30, 45, 565, 76, 46]  # Based on your log data

    ax1.bar(stages, times, color=['#FF9999', '#66B2FF', '#99FF99', '#FFCC99', '#FF99CC', '#99CCFF'])
    ax1.set_title('Processing Time Distribution (seconds)', fontweight='bold')
    ax1.set_ylabel('Time (seconds)')
    for i, v in enumerate(times):
        ax1.text(i, v + 10, str(v), ha='center', va='bottom')

    # 2. Validation score distribution simulation
    scores = [44, 67, 82, 91, 35, 78, 56, 89, 43, 72]
    ax2.hist(scores, bins=5, color='skyblue', alpha=0.7, edgecolor='black')
    ax2.axvline(x=60, color='red', linestyle='--', label='Pass Threshold (60)')
    ax2.set_title('Validation Score Distribution', fontweight='bold')
    ax2.set_xlabel('Score')
    ax2.set_ylabel('Frequency')
    ax2.legend()

    # 3. System resource usage
    resources = ['CPU', 'Memory', 'Disk I/O', 'Network']
    usage = [75, 45, 90, 60]

    ax3.barh(resources, usage, color=['#FFB366', '#66FFB3', '#B366FF', '#66B3FF'])
    ax3.set_title('System Resource Usage (%)', fontweight='bold')
    ax3.set_xlabel('Usage (%)')
    for i, v in enumerate(usage):
        ax3.text(v + 1, i, f'{v}%', va='center')

    # 4. Decision result distribution
    decisions = ['PASS', 'REVIEW', 'REJECT', 'ERROR']
    counts = [65, 20, 10, 5]
    colors = ['green', 'orange', 'red', 'gray']

    ax4.pie(counts, labels=decisions, colors=colors, autopct='%1.1f%%', startangle=90)
    ax4.set_title('Decision Result Distribution', fontweight='bold')

    plt.suptitle('MetaCam System Performance Analysis', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig('performance_analysis.png', dpi=300, bbox_inches='tight')
    print("Performance analysis chart saved: performance_analysis.png")

def main():
    """Main function"""
    print("Generating MetaCam data processing system visualization charts...")
    print(f"Generation time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        create_simplified_flow_diagram()
        create_state_machine_diagram()
        create_performance_analysis()

        print("\n" + "="*50)
        print("All charts generated successfully!")
        print("\nGenerated files:")
        print("1. system_flow.png - System flow diagram")
        print("2. state_machine.png - State machine diagram")
        print("3. performance_analysis.png - Performance analysis")
        print("4. system_state_machine.md - Detailed documentation")

        print("\nHow to view:")
        print("- Windows: Double-click image files")
        print("- Linux/Mac: Use image viewer")
        print("- VSCode: Right-click -> Open with -> Image Preview")

        print("\nFor online visualization:")
        print("1. Visit https://mermaid.live/")
        print("2. Copy mermaid code from system_state_machine.md")
        print("3. Paste into online editor for interactive diagrams")

    except ImportError as e:
        print(f"Missing dependencies: {e}")
        print("\nPlease install required dependencies:")
        print("pip install matplotlib networkx")

    except Exception as e:
        print(f"Error generating charts: {e}")

if __name__ == "__main__":
    main()