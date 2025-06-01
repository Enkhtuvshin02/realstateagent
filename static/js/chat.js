// DOM элементүүдийг тодорхойлох
document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const sendButton = document.getElementById('send-button');
    const loading = document.getElementById('loading');
    const statusSpan = document.getElementById('status');
    const cacheStatusSpan = document.getElementById('cache-status');

    // Чатын форм илгээх үйлдэл
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const message = userInput.value.trim();
        if (message) {
            sendMessage(message);
        }
    });

    // Текст оруулах талбарын өндрийг автоматаар тохируулах
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value.trim()) {
            sendButton.disabled = false;
        } else {
            sendButton.disabled = true;
        }
    });

    // Мессеж илгээх функц
    async function sendMessage(message) {
        if (!message.trim()) return;

        // Хэрэглэгчийн мессежийг харуулах
        addMessage(message, 'user');
        userInput.value = '';
        userInput.style.height = 'auto';
        sendButton.disabled = true;

        // Форм түгжих
        setFormEnabled(false);
        showLoading(true);
        statusSpan.textContent = 'Шинжилгээ хийж байна...';

        try {
            // Серверт хүсэлт илгээх
            const formData = new FormData();
            formData.append('user_message', message);

            const response = await fetch('/chat', {
                method: 'POST',
                body: formData
            });

            // Хариу авах
            const data = await response.json();
            showLoading(false);

            if (data.response) {
                // Туслахын хариуг харуулах
                addMessage(data.response, 'assistant', data);
            } else {
                addMessage('Уучлаарай, алдаа гарлаа. Дахин оролдоно уу.', 'assistant');
            }

        } catch (error) {
            console.error('Error:', error);
            showLoading(false);
            addMessage('Серверт холбогдоход алдаа гарлаа. Дахин оролдоно уу.', 'assistant');
        } finally {
            // Форм идэвхжүүлэх
            setFormEnabled(true);
            statusSpan.textContent = 'Бэлэн байна';
            userInput.focus();
        }
    }

    // Мессеж нэмэх функц
    function addMessage(content, sender, data = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        if (sender === 'assistant') {
            const labelDiv = document.createElement('div');
            labelDiv.className = 'assistant-label';
            labelDiv.textContent = 'Туслах';
            messageDiv.appendChild(labelDiv);

            // Хариултыг форматлах
            formatAssistantResponse(content, contentDiv);
            
            // Тайлан үүсгэсэн бол татаж авах холбоос нэмэх
            if (data.download_url) {
                const downloadLink = document.createElement('a');
                downloadLink.href = data.download_url;
                downloadLink.className = 'download-link';
                downloadLink.textContent = '📥 PDF Тайлан татаж авах';
                downloadLink.target = '_blank';
                contentDiv.appendChild(downloadLink);
            }
        } else {
            contentDiv.textContent = content;
        }

        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Туслахын хариуг форматлах
    function formatAssistantResponse(content, container) {
        // Хариултыг хэсгүүдэд хуваах
        const sections = content.split('\n\n');

        // Тайлан авах асуултыг шалгах
        if (content.includes('**Тайлан авах уу?**')) {
            const parts = content.split('**Тайлан авах уу?**');
            
            const mainContent = parts[0].replace(/\n/g, '<br>');
            container.innerHTML = mainContent;

            const reportOfferDiv = document.createElement('div');
            reportOfferDiv.className = 'report-offer';
            reportOfferDiv.innerHTML = `
                <div class="report-title">Тайлан авах уу?</div>
                <div>${parts[1].replace(/\n/g, '<br>')}</div>
                <div class="report-buttons">
                    <button class="report-button accept" onclick="sendQuickMessage('Тиймээ')">Тиймээ</button>
                    <button class="report-button decline" onclick="sendQuickMessage('Үгүй')">Үгүй</button>
                </div>
            `;
            container.appendChild(reportOfferDiv);
            return;
        }

        // Дэлгэрэнгүй шинжилгээний алхмууд
        if (content.includes('**Дэлгэрэнгүй шинжилгээний алхмууд:**')) {
            const cotDiv = document.createElement('div');
            cotDiv.className = 'cot-section';
            
            const titleDiv = document.createElement('div');
            titleDiv.className = 'cot-title';
            titleDiv.innerHTML = '🧠 Дэлгэрэнгүй шинжилгээний алхмууд';
            cotDiv.appendChild(titleDiv);
            container.appendChild(cotDiv);
            
            // Шинжилгээний алхмуудыг ялгах
            const steps = content.split('\n\n').filter(section => 
                section.includes('**') && section.includes('.') && !section.includes('**Дэлгэрэнгүй шинжилгээний алхмууд:**')
            );
            
            steps.forEach(step => {
                const lines = step.split('\n');
                const title = lines[0].replace(/\*\*/g, '');
                const content = lines.slice(1).join(' ');

                const stepDiv = document.createElement('div');
                stepDiv.className = 'thinking-step';
                stepDiv.innerHTML = `
                    <div class="step-title">${title}</div>
                    <div class="step-content">${content}</div>
                `;
                cotDiv.appendChild(stepDiv);
            });
        }

        sections.forEach(section => {
            // Chain-of-Thought хэсгийг илрүүлэх
            if (section.startsWith('**🧠')) {
                const cotDiv = document.createElement('div');
                cotDiv.className = 'cot-section';

                const titleDiv = document.createElement('div');
                titleDiv.className = 'cot-title';
                titleDiv.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3C7.02944 3 3 7.02944 3 12C3 16.9706 7.02944 21 12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3Z" stroke="#3b82f6" stroke-width="2"/><path d="M12 8V16" stroke="#3b82f6" stroke-width="2" stroke-linecap="round"/><path d="M8 12H16" stroke="#3b82f6" stroke-width="2" stroke-linecap="round"/></svg> Дэлгэрэнгүй шинжилгээ';
                cotDiv.appendChild(titleDiv);

                // Шинжилгээний хэсгүүдийг боловсруулах
                const steps = section.split('\n').slice(1);
                steps.forEach(step => {
                    if (step.trim() && step.includes(':')) {
                        const [title, ...content] = step.split(':');
                        const stepDiv = document.createElement('div');
                        stepDiv.className = 'thinking-step';

                        const stepTitleDiv = document.createElement('div');
                        stepTitleDiv.className = 'step-title';
                        stepTitleDiv.textContent = title.replace('*', '').replace('*', '').trim();
                        stepDiv.appendChild(stepTitleDiv);

                        const stepContentDiv = document.createElement('div');
                        stepContentDiv.className = 'step-content';
                        stepContentDiv.textContent = content.join(':').trim();
                        stepDiv.appendChild(stepContentDiv);

                        cotDiv.appendChild(stepDiv);
                    }
                });

                container.appendChild(cotDiv);
            }
            // Тайлан санал болгох хэсэг
            else if (section.includes('**📊 Тайлан үүсгэх:**')) {
                const reportDiv = document.createElement('div');
                reportDiv.className = 'report-offer';

                const titleDiv = document.createElement('div');
                titleDiv.className = 'report-title';
                titleDiv.textContent = '📊 Тайлан үүсгэх:';
                reportDiv.appendChild(titleDiv);

                const contentDiv = document.createElement('div');
                contentDiv.textContent = section.replace('**📊 Тайлан үүсгэх:**', '').trim();
                reportDiv.appendChild(contentDiv);

                const buttonsDiv = document.createElement('div');
                buttonsDiv.className = 'report-buttons';

                // PDF татах товч
                const pdfButton = document.createElement('button');
                pdfButton.className = 'report-button pdf';
                pdfButton.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z" fill="#0369a1"/></svg> PDF татах';
                pdfButton.onclick = function() {
                    window.open('/download/report/pdf', '_blank');
                };
                buttonsDiv.appendChild(pdfButton);

                reportDiv.appendChild(buttonsDiv);
                container.appendChild(reportDiv);
            }
            // Гол дүгнэлтүүд хэсэг
            else if (section.includes('**💡 Гол дүгнэлтүүд:**')) {
                const insightsDiv = document.createElement('div');
                insightsDiv.className = 'insights-section';
                
                const titleDiv = document.createElement('div');
                titleDiv.className = 'insights-title';
                titleDiv.textContent = 'Гол дүгнэлтүүд:';
                insightsDiv.appendChild(titleDiv);

                const insights = section.split('•').slice(1);
                insights.forEach(insight => {
                    if (insight.trim()) {
                        const insightDiv = document.createElement('div');
                        insightDiv.className = 'insight-item';
                        insightDiv.textContent = '• ' + insight.trim();
                        insightsDiv.appendChild(insightDiv);
                    }
                });

                container.appendChild(insightsDiv);
            } else if (section.trim() && 
                      !section.includes('**Дэлгэрэнгүй шинжилгээний алхмууд:**')) {
                const paraDiv = document.createElement('div');
                paraDiv.innerHTML = section.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                paraDiv.style.marginBottom = '12px';
                container.appendChild(paraDiv);
            }
        });
    }

    // Формыг идэвхжүүлэх/идэвхгүй болгох функц
    function setFormEnabled(enabled) {
        userInput.disabled = !enabled;
        sendButton.disabled = !enabled || userInput.value.trim() === '';
    }

    // Ачаалах анимейшн харуулах/нуух функц
    function showLoading(show) {
        loading.style.display = show ? 'block' : 'none';
    }
    
    // Түргэн хариулт илгээх функц
    function sendQuickMessage(message) {
        if (!message) return;
        sendMessage(message);
    }

    // Кэшийг шинэчлэх
    async function refreshCache() {
        try {
            statusSpan.textContent = 'Кэш шинэчилж байна...';
            const response = await fetch('/refresh-cache');
            const data = await response.json();
            
            if (data.success) {
                statusSpan.textContent = 'Кэш шинэчлэгдлээ';
                setTimeout(() => {
                    statusSpan.textContent = 'Бэлэн байна';
                }, 2000);
                
                checkCacheStatus();
            } else {
                statusSpan.textContent = 'Кэш шинэчлэхэд алдаа гарлаа';
                setTimeout(() => {
                    statusSpan.textContent = 'Бэлэн байна';
                }, 2000);
            }
        } catch (error) {
            console.error('Error refreshing cache:', error);
            statusSpan.textContent = 'Кэш шинэчлэхэд алдаа гарлаа';
            setTimeout(() => {
                statusSpan.textContent = 'Бэлэн байна';
            }, 2000);
        }
    }

    // Кэшийн төлөвийг шалгах
    async function checkCacheStatus() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            
            const cacheIndicator = document.getElementById('cache-indicator');
            const cacheStatusSpan = document.getElementById('cache-status');
            
            if (data.cache_status === 'fresh') {
                cacheIndicator.className = 'status-indicator';
                cacheStatusSpan.textContent = 'Шинэ';
            } else if (data.cache_status === 'stale') {
                cacheIndicator.className = 'status-indicator stale';
                cacheStatusSpan.textContent = 'Хуучин';
            } else {
                cacheIndicator.className = 'status-indicator error';
                cacheStatusSpan.textContent = 'Алдаатай';
            }
        } catch (error) {
            console.error('Error checking cache status:', error);
            const cacheIndicator = document.getElementById('cache-indicator');
            cacheIndicator.className = 'status-indicator error';
            cacheStatusSpan.textContent = 'Алдаатай';
        }
    }

    // Хуудас ачаалагдахад кэшийн төлөвийг шалгах
    checkCacheStatus();
    
    // Кэш шинэчлэх товчлуур
    document.getElementById('refresh-cache').addEventListener('click', refreshCache);
    
    // Кэшийн төлөвийг тогтмол шалгах (5 минут тутамд)
    setInterval(checkCacheStatus, 5 * 60 * 1000);

    // Глобал функцуудыг window объектод нэмэх
    window.sendQuickMessage = sendQuickMessage;
});
