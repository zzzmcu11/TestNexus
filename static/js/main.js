// AI 需求文档自动化测试分析系统 - 前端逻辑

class AITestAnalyzer {
    constructor() {
        this.currentTestPointId = null;
        this.analysisResult = null;
        this.selectedFile = null; // 存储选择的文件
        this.taskState = 'idle'; // idle, running, paused, stopped
        this.taskController = null; // 用于控制任务
        
        this.initEventListeners();
        this.updateStatusIndicator();
    }

    initEventListeners() {
        // 文件选择器事件 - 使用一次性事件处理避免重复触发
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');

        // 使用防抖处理文件选择事件
        let fileSelectTimeout;
        const handleFileSelectDebounced = (e) => {
            clearTimeout(fileSelectTimeout);
            fileSelectTimeout = setTimeout(() => {
                this.handleFileSelect(e);
            }, 100);
        };
        
        fileInput.addEventListener('change', handleFileSelectDebounced);
        
        // 控制按钮事件
        document.getElementById('startBtn')?.addEventListener('click', () => this.startAnalysis());
        document.getElementById('pauseBtn')?.addEventListener('click', () => this.pauseAnalysis());
        document.getElementById('stopBtn')?.addEventListener('click', () => this.stopAnalysis());
        
        uploadArea.addEventListener('click', () => {
            // 清除现有文件，确保每次都是新上传
            fileInput.value = '';
            fileInput.click();
        });
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('border-blue-400', 'bg-blue-50');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('border-blue-400', 'bg-blue-50');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('border-blue-400', 'bg-blue-50');
            
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                // 直接触发文件选择事件
                const event = new Event('change', { bubbles: true });
                fileInput.dispatchEvent(event);
            }
        });

        // 导出按钮
        document.getElementById('exportBtn')?.addEventListener('click', () => this.exportResults());
        
        // 返回按钮
        document.getElementById('backToPointsBtn')?.addEventListener('click', () => this.showTestPoints());
        
        // 历史记录按钮
        document.getElementById('refreshHistoryBtn')?.addEventListener('click', () => this.loadHistory());
        document.getElementById('clearHistoryBtn')?.addEventListener('click', () => this.clearHistory());
        
        // 模型选择按钮
        this.initModelSelection();
    }
    
    initModelSelection() {
        const modelOptions = document.querySelectorAll('.model-option');
        modelOptions.forEach(option => {
            option.addEventListener('click', () => {
                // 移除所有选项的选中状态
                modelOptions.forEach(opt => {
                    opt.classList.remove('bg-blue-500', 'text-white');
                    opt.classList.add('bg-gray-200', 'text-gray-800');
                    opt.querySelectorAll('span').forEach(span => {
                        if (span.classList.contains('bg-blue-700')) {
                            span.classList.remove('bg-blue-700');
                            span.classList.add('bg-gray-500');
                        }
                    });
                });
                
                // 设置当前选项为选中状态
                option.classList.remove('bg-gray-200', 'text-gray-800');
                option.classList.add('bg-blue-500', 'text-white');
                option.querySelectorAll('span').forEach(span => {
                    if (span.classList.contains('bg-gray-500')) {
                        span.classList.remove('bg-gray-500');
                        span.classList.add('bg-blue-700');
                    }
                });
                
                // 保存选中的模型
                this.selectedModel = option.dataset.model;
                this.showSuccess(`已选择模型: ${this.getModelDisplayName(this.selectedModel)}`);
            });
        });
        
        // 默认选择第一个模型
        if (modelOptions.length > 0) {
            modelOptions[0].click();
        }
    }
    
    getModelDisplayName(modelKey) {
        const modelNames = {
            'deepseek-reasoner': 'DeepSeek-Reasoner',
            'qwen-max': 'Qwen3-Max',
            'siliconflow': '硅基流动'
        };
        return modelNames[modelKey] || modelKey;
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        // 验证文件类型
        if (!file.name.endsWith('.docx')) {
            this.showError('请选择 .docx 格式的文件');
            return;
        }

        // 验证文件大小 (16MB)
        if (file.size > 16 * 1024 * 1024) {
            this.showError('文件大小不能超过 16MB');
            return;
        }

        // 显示文件名
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.innerHTML = `
            <div class="text-green-500 text-5xl mb-4">
                <i class="fas fa-file-word"></i>
            </div>
            <h3 class="text-lg font-medium text-gray-700 mb-2">${file.name}</h3>
            <p class="text-gray-500 text-sm mb-4">${this.formatFileSize(file.size)}</p>
            <div class="bg-green-100 text-green-800 text-sm font-medium py-2 px-4 rounded-lg inline-block">
                <i class="fas fa-check mr-2"></i>文件已选择，准备上传
            </div>
        `;

        // 显示控制按钮
        document.getElementById('controlButtons').style.display = 'flex';
        // 保存文件，但不立即上传
        this.selectedFile = file;
        // 启用开始按钮
        document.getElementById('startBtn').disabled = false;
        // 禁用暂停/停止按钮
        document.getElementById('pauseBtn').disabled = true;
        document.getElementById('stopBtn').disabled = true;
    }

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        // 显示加载指示器
        this.showLoading(true);
        this.updateStatusIndicator('正在上传并分析文档...');

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || '上传失败');
            }

            // 保存结果并更新UI
            this.analysisResult = result;
            this.showAnalysisResults();
            this.updateStatusIndicator('分析完成');

        } catch (error) {
            console.error('Upload error:', error);
            this.showError(`处理失败: ${error.message}`);
            this.updateStatusIndicator('处理失败');
        } finally {
            this.showLoading(false);
        }
    }

    // 开始分析
    startAnalysis() {
        if (!this.selectedFile) {
            this.showError('请先选择文件');
            return;
        }
        
        if (this.taskState === 'paused') {
            // 恢复暂停的任务
            this.taskController.resume();
            this.updateStatusIndicator('分析已恢复');
        } else {
            // 开始新任务
            this.uploadFileStream(this.selectedFile);
        }
        
        this.taskState = 'running';
        document.getElementById('pauseBtn').disabled = false;
        document.getElementById('stopBtn').disabled = false;
        document.getElementById('startBtn').disabled = true;
    }

    // 暂停分析
    pauseAnalysis() {
        if (this.taskState === 'running' && this.taskController) {
            this.taskController.pause();
            this.taskState = 'paused';
            this.updateStatusIndicator('分析已暂停');
            document.getElementById('pauseBtn').disabled = true;
            document.getElementById('startBtn').disabled = false;
        }
    }

    // 停止分析
    stopAnalysis() {
        if (this.taskController) {
            this.taskController.abort();
            this.taskState = 'stopped';
            this.updateStatusIndicator('分析已停止');
            document.getElementById('pauseBtn').disabled = true;
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('startBtn').disabled = true;
            this.showLoading(false);
        }
    }


    async uploadFileStream(file) {
        // 显示加载指示器和进度条
        this.showLoading(true);
        this.updateStatusIndicator('开始上传...');
        
        // 创建任务控制器
        this.taskController = new TaskController();
        
        // 创建进度显示区域
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.innerHTML = `
            <div class="mb-4">
                <div class="flex justify-between text-sm text-gray-600 mb-1">
                    <span>${file.name}</span>
                    <span id="progressPercentage">0%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div id="progressBar" class="bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                </div>
            </div>
            <div id="progressMessages" class="text-sm text-gray-600 space-y-1 max-h-40 overflow-y-auto"></div>
        `;

        const formData = new FormData();
        formData.append('file', file);
        
        // 添加选择的模型到formData
        if (this.selectedModel) {
            formData.append('model_name', this.selectedModel);
        }

        try {
            const response = await fetch('/upload/stream', {
                method: 'POST',
                body: formData,
                signal: this.taskController.signal
            });

            if (!response.ok) {
                // 如果是HTTP错误，尝试获取错误信息
                const errorText = await response.text();
                throw new Error(`服务器响应错误: ${response.status} ${errorText.substring(0, 200)}`);
            }
            
            if (!response.body) {
                throw new Error('服务器未返回数据流');
            }

            // 使用ReadableStream处理SSE
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let hasCompleted = false;

            while (true) {
                // 检查是否暂停
                if (this.taskController.isPaused) {
                    await this.taskController.pause();
                }
                
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        const eventType = line.substring(6).trim();
                        // 下一个行应该是data
                        continue;
                    }
                    if (line.startsWith('data:')) {
                        const data = line.substring(5).trim();
                        if (data) {
                            try {
                                const eventData = JSON.parse(data);
                                this.handleStreamEvent(eventData);
                                
                                // 检查是否完成
                                if (eventData.test_points || eventData.error) {
                                    hasCompleted = true;
                                }
                            } catch (e) {
                                console.error('Error parsing SSE data:', e);
                                // 如果解析失败但不是关键错误，继续处理
                                if (!hasCompleted) {
                                    console.warn('非致命解析错误，继续处理:', e);
                                }
                            }
                        }
                    }
                }
            }
            
            // 如果没有收到完成事件但流已结束，检查是否有分析结果
            if (!hasCompleted && this.analysisResult) {
                // 如果有分析结果，说明处理成功
                this.showAnalysisResults();
                this.updateStatusIndicator('分析完成');
                this.showLoading(false);
                this.showSuccess('文档分析完成');
            } else if (!hasCompleted) {
                // 如果没有分析结果且没有完成事件，显示通用错误
                this.showError('处理过程中出现未知错误，请检查服务器日志');
                this.updateStatusIndicator('处理失败');
                this.showLoading(false);
            }

        } catch (error) {
            console.error('Stream upload error:', error);
            
            // 更友好的错误消息
            let errorMessage = error.message;
            if (error.message.includes('Failed to fetch')) {
                errorMessage = '无法连接到服务器，请确保后端服务正在运行';
            } else if (error.message.includes('NetworkError')) {
                errorMessage = '网络连接错误，请检查网络连接';
            } else if (error.message.includes('timeout')) {
                errorMessage = '请求超时，请稍后重试';
            }
            
            this.showError(`上传失败: ${errorMessage}`);
            this.updateStatusIndicator('上传失败');
            this.showLoading(false);
            
            // 恢复上传区域到初始状态
            this.resetUploadArea();
        }
    }
    
    resetUploadArea() {
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.innerHTML = `
            <div class="text-gray-400 text-5xl mb-4">
                <i class="fas fa-file-word"></i>
            </div>
            <h3 class="text-lg font-medium text-gray-700 mb-2">拖放或点击上传</h3>
            <p class="text-gray-500 text-sm mb-4">支持 .docx 格式的需求文档</p>
            <label class="inline-block bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-6 rounded-lg cursor-pointer transition-colors">
                <input type="file" id="fileInput" class="hidden" accept=".docx">
                <i class="fas fa-folder-open mr-2"></i>选择文件
            </label>
        `;
        
        // 重新绑定事件
        const fileInput = uploadArea.querySelector('#fileInput');
        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
    }

    handleStreamEvent(eventData) {
        const progressMessages = document.getElementById('progressMessages');
        const progressBar = document.getElementById('progressBar');
        const progressPercentage = document.getElementById('progressPercentage');
        
        if (eventData.message) {
            // 添加进度消息
            const messageDiv = document.createElement('div');
            messageDiv.className = 'flex items-start py-1';
            messageDiv.innerHTML = `
                <i class="fas fa-circle text-blue-500 text-xs mt-1 mr-2"></i>
                <span>${eventData.message}</span>
            `;
            if (progressMessages) {
                progressMessages.appendChild(messageDiv);
                progressMessages.scrollTop = progressMessages.scrollHeight;
            }
            
            this.updateStatusIndicator(eventData.message);
        }
        
        if (eventData.progress !== undefined && progressBar && progressPercentage) {
            // 更新进度条
            progressBar.style.width = `${eventData.progress}%`;
            progressPercentage.textContent = `${eventData.progress}%`;
        }
        
        if (eventData.error) {
            // 显示错误
            this.showError(eventData.error);
            this.updateStatusIndicator('分析失败');
            this.showLoading(false);
        }
        
        if (eventData.test_points) {
            // 分析完成，显示结果
            this.analysisResult = eventData;
            setTimeout(() => {
                this.showAnalysisResults();
                this.updateStatusIndicator('分析完成');
                this.showLoading(false);
            }, 500);
        }
    }

    showAnalysisResults() {
        // 隐藏初始消息
        document.getElementById('initialMessage').style.display = 'none';
        
        // 显示结果区域
        document.getElementById('resultsSummary').style.display = 'block';
        document.getElementById('testPointsSection').style.display = 'block';
        
        // 更新摘要统计
        this.updateSummaryStats();
        
        // 更新测试点列表
        this.updateTestPointsList();
    }

    updateSummaryStats() {
        if (!this.analysisResult) return;

        const { document_summary, analysis_summary } = this.analysisResult;
        
        // 更新统计卡片
        const summaryStats = document.getElementById('summaryStats');
        summaryStats.innerHTML = `
            <div class="bg-blue-50 p-4 rounded-lg border border-blue-200">
                <div class="text-2xl font-bold text-blue-700 mb-1">${document_summary.total_test_points}</div>
                <div class="text-sm text-blue-600">测试点数量</div>
            </div>
            <div class="bg-green-50 p-4 rounded-lg border border-green-200">
                <div class="text-2xl font-bold text-green-700 mb-1">${document_summary.total_test_cases}</div>
                <div class="text-sm text-green-600">测试用例数量</div>
            </div>
            <div class="bg-purple-50 p-4 rounded-lg border border-purple-200">
                <div class="text-2xl font-bold text-purple-700 mb-1">${document_summary.total_characters}</div>
                <div class="text-sm text-purple-600">文档字符数</div>
            </div>
            <div class="bg-orange-50 p-4 rounded-lg border border-orange-200">
                <div class="text-2xl font-bold text-orange-700 mb-1">${this.analysisResult.test_cases.length}</div>
                <div class="text-sm text-orange-600">生成用例总数</div>
            </div>
        `;

        // 更新优先级图表
        const priorityChart = document.getElementById('priorityChart');
        const priorities = ['critical', 'high', 'medium', 'low'];
        const priorityLabels = {
            'critical': '紧急',
            'high': '高',
            'medium': '中',
            'low': '低'
        };
        const priorityColors = {
            'critical': 'bg-red-500',
            'high': 'bg-orange-500',
            'medium': 'bg-yellow-500',
            'low': 'bg-green-500'
        };

        let chartHTML = '';
        priorities.forEach(priority => {
            const count = analysis_summary[`${priority}_count`] || 0;
            const total = document_summary.total_test_points;
            const percentage = total > 0 ? Math.round((count / total) * 100) : 0;
            
            chartHTML += `
                <div class="flex items-center justify-between">
                    <div class="flex items-center">
                        <div class="w-3 h-3 rounded-full ${priorityColors[priority]} mr-2"></div>
                        <span class="text-sm font-medium text-gray-700">${priorityLabels[priority]}</span>
                    </div>
                    <div class="flex items-center space-x-3">
                        <span class="text-sm font-bold text-gray-800">${count}</span>
                        <div class="w-24 bg-gray-200 rounded-full h-2">
                            <div class="${priorityColors[priority]} h-2 rounded-full" style="width: ${percentage}%"></div>
                        </div>
                        <span class="text-xs text-gray-500 w-8">${percentage}%</span>
                    </div>
                </div>
            `;
        });

        priorityChart.innerHTML = chartHTML;
    }

    updateTestPointsList() {
        if (!this.analysisResult) return;

        const container = document.getElementById('testPointsContainer');
        const testPoints = this.analysisResult.test_points || [];
        
        container.innerHTML = '';
        
        testPoints.forEach((point, index) => {
            const priorityClass = `priority-${point.priority}`;
            const priorityIcons = {
                'critical': 'fas fa-fire text-red-500',
                'high': 'fas fa-exclamation-triangle text-orange-500',
                'medium': 'fas fa-exclamation-circle text-yellow-500',
                'low': 'fas fa-check-circle text-green-500'
            };
            
            const card = document.createElement('div');
            card.className = `test-point-card bg-white rounded-xl shadow border border-gray-200 p-5 ${priorityClass}`;
            card.dataset.testPointId = point.id;
            
            // 安全处理边界情况
            const edgeCases = point.edge_cases || [];
            const edgeCasesHtml = Array.isArray(edgeCases) 
                ? edgeCases.map(edgeCase => 
                    `<span class="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">${edgeCase}</span>`
                ).join('')
                : `<span class="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">${edgeCases}</span>`;
            
            card.innerHTML = `
                <div class="flex justify-between items-start mb-3">
                    <div class="flex items-center">
                        <div class="bg-gray-100 text-gray-800 font-bold text-sm py-1 px-3 rounded-lg mr-3">
                            ${point.id || `TP-${index + 1}`}
                        </div>
                        <div>
                            <i class="${priorityIcons[point.priority] || 'fas fa-circle'} mr-1"></i>
                            <span class="text-sm font-medium text-gray-700">${point.priority ? point.priority.toUpperCase() : 'UNKNOWN'}</span>
                        </div>
                    </div>
                    <span class="bg-blue-100 text-blue-800 text-xs font-medium px-3 py-1 rounded-full">
                        ${point.category || '未分类'}
                    </span>
                </div>
                
                <h3 class="font-bold text-gray-800 mb-3">${point.description || '无描述'}</h3>
                
                <div class="mb-4">
                    <div class="text-sm text-gray-600 mb-1">需求引用：</div>
                    <div class="text-sm bg-gray-50 p-3 rounded-lg border border-gray-200">
                        ${point.requirements_ref || '无'}
                    </div>
                </div>
                
                <div>
                    <div class="text-sm text-gray-600 mb-2">边界情况：</div>
                    <div class="flex flex-wrap gap-2">
                        ${edgeCasesHtml}
                    </div>
                </div>
                
                <div class="mt-4 pt-4 border-t border-gray-200 flex justify-end">
                    <button class="view-cases-btn bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium py-2 px-4 rounded-lg transition-colors">
                        <i class="fas fa-vial mr-2"></i>查看测试用例
                    </button>
                </div>
            `;
            
            // 添加查看测试用例的事件监听
            const viewBtn = card.querySelector('.view-cases-btn');
            viewBtn.addEventListener('click', () => this.showTestCases(point.id || `TP-${index + 1}`));
            
            container.appendChild(card);
        });
    }

    showTestCases(testPointId) {
        if (!this.analysisResult) return;

        this.currentTestPointId = testPointId;
        
        // 隐藏测试点列表，显示测试用例详情
        document.getElementById('testPointsSection').style.display = 'none';
        document.getElementById('testCasesSection').style.display = 'block';
        
        // 获取该测试点相关的测试用例
        const testCases = this.analysisResult.test_cases.filter(
            testCase => testCase.linked_point_id === testPointId
        );
        
        // 获取测试点信息
        const testPoint = this.analysisResult.test_points.find(
            point => point.id === testPointId
        );
        
        const container = document.getElementById('testCasesContainer');
        
        // 显示测试点概览
        let html = `
            <div class="bg-white rounded-xl shadow border border-gray-200 p-6 mb-6">
                <div class="flex items-start justify-between mb-4">
                    <div>
                        <div class="flex items-center mb-2">
                            <div class="bg-gray-800 text-white font-bold text-sm py-1 px-3 rounded-lg mr-3">
                                ${testPoint?.id || '未知'}
                            </div>
                            <h3 class="text-xl font-bold text-gray-800">${testPoint?.description || '无描述'}</h3>
                        </div>
                        <div class="text-gray-600">
                            <i class="fas fa-layer-group mr-2"></i>类别: ${testPoint?.category || '未知'} | 
                            <i class="fas fa-flag ml-4 mr-2"></i>优先级: ${testPoint?.priority || '未知'}
                        </div>
                    </div>
                </div>
                <p class="text-gray-700 bg-gray-50 p-4 rounded-lg border border-gray-200">
                    <strong>需求引用:</strong> ${testPoint?.requirements_ref || '无'}
                </p>
            </div>
        `;
        
        // 显示测试用例
        if (!testCases || testCases.length === 0) {
            html += `
                <div class="bg-yellow-50 border border-yellow-200 rounded-xl p-8 text-center">
                    <i class="fas fa-exclamation-triangle text-yellow-500 text-4xl mb-4"></i>
                    <h3 class="text-lg font-bold text-yellow-800 mb-2">暂无测试用例</h3>
                    <p class="text-yellow-700">未找到此测试点相关的测试用例。</p>
                </div>
            `;
        } else {
            html += `<h3 class="text-lg font-bold text-gray-800 mb-4">${testCases.length} 个测试用例:</h3>`;
            
            testCases.forEach((testCase, index) => {
                // 安全处理前置条件
                const preconditions = testCase?.preconditions || [];
                const preconditionsHtml = Array.isArray(preconditions) 
                    ? preconditions.map(pre => `<li>${pre}</li>`).join('')
                    : `<li>${preconditions}</li>`;
                
                // 安全处理测试步骤
                const steps = testCase?.steps || [];
                const stepsHtml = Array.isArray(steps)
                    ? steps.map((step, i) => `
                        <li class="flex">
                            <span class="step-number">${i + 1}</span>
                            <span class="text-gray-600">${step}</span>
                        </li>
                    `).join('')
                    : `<li class="flex">
                        <span class="step-number">1</span>
                        <span class="text-gray-600">${steps}</span>
                    </li>`;
                
                html += `
                    <div class="bg-white rounded-xl shadow border border-gray-200 overflow-hidden">
                        <div class="bg-gray-50 px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                            <div class="flex items-center">
                                <div class="bg-blue-100 text-blue-800 font-bold text-sm py-1 px-3 rounded-lg mr-3">
                                    ${testCase?.test_case_id || `TC-${index + 1}`}
                                </div>
                                <h4 class="font-bold text-gray-800">${testCase?.title || '未命名测试用例'}</h4>
                            </div>
                            <div class="text-sm text-gray-500">用例 #${index + 1}</div>
                        </div>
                        
                        <div class="p-6">
                            <div class="mb-6">
                                <h5 class="font-semibold text-gray-700 mb-2">前置条件:</h5>
                                <ul class="list-disc pl-5 text-gray-600 space-y-1">
                                    ${preconditionsHtml}
                                </ul>
                            </div>
                            
                            <div class="mb-6">
                                <h5 class="font-semibold text-gray-700 mb-2">测试步骤:</h5>
                                <ol class="space-y-3">
                                    ${stepsHtml}
                                </ol>
                            </div>
                            
                            <div class="mb-4">
                                <h5 class="font-semibold text-gray-700 mb-2">预期结果:</h5>
                                <div class="bg-green-50 border border-green-200 rounded-lg p-4">
                                    <p class="text-green-800">${testCase?.expected_result || '无预期结果'}</p>
                                </div>
                            </div>
                            
                            <div>
                                <h5 class="font-semibold text-gray-700 mb-2">测试数据:</h5>
                                <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
                                    <p class="text-gray-800">${testCase?.test_data || '无特殊测试数据要求'}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        
        container.innerHTML = html;
    }

    showTestPoints() {
        // 显示测试点列表，隐藏测试用例详情
        document.getElementById('testPointsSection').style.display = 'block';
        document.getElementById('testCasesSection').style.display = 'none';
    }

    async exportResults() {
        if (!this.analysisResult) {
            this.showError('没有可导出的数据');
            return;
        }

        try {
            this.showLoading(true);
            this.updateStatusIndicator('正在生成Excel文件...');

            const response = await fetch('/export/excel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(this.analysisResult)
            });

            if (!response.ok) {
                throw new Error('导出失败');
            }

            // 获取Blob并创建下载链接
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `test-analysis-${new Date().toISOString().split('T')[0]}.xlsx`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
            this.showSuccess('Excel文件已生成并开始下载');
            
        } catch (error) {
            console.error('Export error:', error);
            this.showError(`导出失败: ${error.message}`);
        } finally {
            this.showLoading(false);
            this.updateStatusIndicator('导出完成');
        }
    }

    showLoading(show) {
        const loadingSpinner = document.getElementById('loadingSpinner');
        if (show) {
            loadingSpinner.style.display = 'block';
        } else {
            loadingSpinner.style.display = 'none';
        }
    }

    showError(message) {
        // 创建错误提示
        const errorDiv = document.createElement('div');
        errorDiv.className = 'fixed top-4 right-4 bg-red-50 border border-red-200 text-red-800 px-6 py-4 rounded-xl shadow-lg z-50 max-w-md';
        errorDiv.innerHTML = `
            <div class="flex items-start">
                <i class="fas fa-exclamation-circle text-red-500 mt-1 mr-3"></i>
                <div>
                    <h4 class="font-bold text-red-800">错误</h4>
                    <p class="text-red-700 mt-1">${message}</p>
                </div>
                <button class="ml-auto text-red-400 hover:text-red-600">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(errorDiv);
        
        // 添加关闭按钮事件
        const closeBtn = errorDiv.querySelector('button');
        closeBtn.addEventListener('click', () => errorDiv.remove());
        
        // 3秒后自动关闭
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 3000);
    }

    showSuccess(message) {
        // 创建成功提示
        const successDiv = document.createElement('div');
        successDiv.className = 'fixed top-4 right-4 bg-green-50 border border-green-200 text-green-800 px-6 py-4 rounded-xl shadow-lg z-50 max-w-md';
        successDiv.innerHTML = `
            <div class="flex items-start">
                <i class="fas fa-check-circle text-green-500 mt-1 mr-3"></i>
                <div>
                    <h4 class="font-bold text-green-800">成功</h4>
                    <p class="text-green-700 mt-1">${message}</p>
                </div>
                <button class="ml-auto text-green-400 hover:text-green-600">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(successDiv);
        
        // 添加关闭按钮事件
        const closeBtn = successDiv.querySelector('button');
        closeBtn.addEventListener('click', () => successDiv.remove());
        
        // 3秒后自动关闭
        setTimeout(() => {
            if (successDiv.parentNode) {
                successDiv.remove();
            }
        }, 3000);
    }

    updateStatusIndicator(status) {
        const indicator = document.getElementById('statusIndicator');
        const icon = indicator.parentElement.querySelector('i');
        
        if (status) {
            indicator.textContent = status;
            if (status.includes('失败')) {
                icon.className = 'fas fa-circle text-red-500 mr-2';
            } else if (status.includes('完成')) {
                icon.className = 'fas fa-circle text-green-500 mr-2';
            } else {
                icon.className = 'fas fa-circle text-yellow-500 mr-2';
            }
        } else {
            indicator.textContent = '系统就绪';
            icon.className = 'fas fa-circle text-green-500 mr-2';
        }
    }

    async loadHistory() {
        try {
            const response = await fetch('/history');
            if (!response.ok) {
                throw new Error('获取历史记录失败');
            }
            const historyList = await response.json();
            this.updateHistoryUI(historyList);
        } catch (error) {
            console.error('Load history error:', error);
            this.showError(`加载历史记录失败: ${error.message}`);
        }
    }

    async clearHistory() {
        if (!confirm('确定要清空所有历史记录吗？此操作不可恢复。')) {
            return;
        }
        
        try {
            const response = await fetch('/history', {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('清空历史记录失败');
            }
            
            this.showSuccess('历史记录已清空');
            this.updateHistoryUI([]);
        } catch (error) {
            console.error('Clear history error:', error);
            this.showError(`清空历史记录失败: ${error.message}`);
        }
    }

    updateHistoryUI(historyList) {
        const container = document.getElementById('historyContainer');
        
        if (!historyList || historyList.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-400">
                    <i class="fas fa-history text-3xl mb-3"></i>
                    <p>暂无历史记录</p>
                    <p class="text-sm mt-1">上传文档后，分析记录将在此显示</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        historyList.forEach(record => {
            const summary = record.summary || {};
            
            const date = new Date(record.timestamp);
            const formattedDate = date.toLocaleDateString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            html += `
                <div class="bg-white rounded-lg border border-gray-200 p-4 hover:bg-gray-50 transition-colors cursor-pointer" data-history-id="${record.id}">
                    <div class="flex justify-between items-start mb-2">
                        <div>
                            <h4 class="font-medium text-gray-800 truncate">${record.original_filename || '未命名文档'}</h4>
                            <p class="text-xs text-gray-500">${formattedDate}</p>
                        </div>
                        <div class="flex items-center space-x-2">
                            <span class="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-1 rounded">
                                ${summary.total_test_points || 0} 测试点
                            </span>
                            <button class="text-gray-400 hover:text-red-500 delete-history-btn" data-history-id="${record.id}">
                                <i class="fas fa-trash-alt text-xs"></i>
                            </button>
                        </div>
                    </div>
                    <div class="text-sm text-gray-600">
                        <div class="grid grid-cols-2 gap-2 mt-2">
                            <div class="flex items-center">
                                <i class="fas fa-file-word text-blue-500 mr-1"></i>
                                <span>${summary.total_characters || 0} 字符</span>
                            </div>
                            <div class="flex items-center">
                                <i class="fas fa-vial text-green-500 mr-1"></i>
                                <span>${summary.total_test_cases || 0} 用例</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
        // 添加点击事件：加载历史记录
        container.querySelectorAll('[data-history-id]').forEach(element => {
            element.addEventListener('click', (e) => {
                if (e.target.closest('.delete-history-btn')) {
                    return; // 删除按钮的点击事件单独处理
                }
                const recordId = element.dataset.historyId;
                this.loadHistoryRecord(recordId);
            });
        });
        
        // 添加删除按钮事件
        container.querySelectorAll('.delete-history-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                e.stopPropagation();
                const recordId = button.dataset.historyId;
                await this.deleteHistoryRecord(recordId);
            });
        });
    }

    async loadHistoryRecord(recordId) {
        try {
            const response = await fetch(`/history/${recordId}`);
            if (!response.ok) {
                throw new Error('获取历史记录详情失败');
            }
            const record = await response.json();
            
            // 使用历史记录的分析结果
            this.analysisResult = record.analysis_result;
            this.showAnalysisResults();
            this.showSuccess('历史记录已加载');
            
        } catch (error) {
            console.error('Load history record error:', error);
            this.showError(`加载历史记录详情失败: ${error.message}`);
        }
    }

    async deleteHistoryRecord(recordId) {
        if (!confirm('确定要删除此条历史记录吗？此操作不可恢复。')) {
            return;
        }
        
        try {
            const response = await fetch(`/history/delete/${recordId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('删除历史记录失败');
            }
            
            this.showSuccess('历史记录已删除');
            // 重新加载历史记录列表
            await this.loadHistory();
        } catch (error) {
            console.error('Delete history record error:', error);
            this.showError(`删除历史记录失败: ${error.message}`);
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// 任务控制器类
class TaskController {
    constructor() {
        this.controller = new AbortController();
        this.isPaused = false;
        this.pauseResume = null;
    }
    
    get signal() {
        return this.controller.signal;
    }
    
    pause() {
        this.isPaused = true;
        return new Promise(resolve => {
            this.pauseResume = resolve;
        });
    }
    
    resume() {
        if (this.isPaused && this.pauseResume) {
            this.isPaused = false;
            this.pauseResume();
        }
    }
    
    abort() {
        this.controller.abort();
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.testAnalyzer = new AITestAnalyzer();
    
    // 检查后端健康状态
    fetch('/health')
        .then(response => response.json())
        .then(data => {
            console.log('Backend health check:', data);
        })
        .catch(error => {
            console.warn('Backend health check failed:', error);
        });
    
    // 页面加载时自动加载历史记录
    setTimeout(() => {
        window.testAnalyzer.loadHistory();
    }, 500);
});
