// script.js
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const chatMessages = document.getElementById('chat-messages');
const loading = document.getElementById('loading');
const statusSpan = document.getElementById('status');
const cacheStatusSpan = document.getElementById('cache-status');

// Auto-resize textarea
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = this.scrollHeight + 'px';
});

// Handle form submission
chatForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    await sendMessage(message);
});

// Send message function
async function sendMessage(message) {
    // Add user message to chat
    addMessage(message, 'user');

    // Clear input and disable form
    userInput.value = '';
    userInput.style.height = 'auto';
    setFormEnabled(false);
    showLoading(true);

    try {
        statusSpan.textContent = '🧠 Chain-of-Thought шинжилгээ хийж байна...';

        const formData = new FormData();
        formData.append('user_message', message);

        const response = await fetch('/chat', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        // Add assistant response
        if (data.response) {
            addMessage(data.response, 'assistant', data);
        } else {
            addMessage('Алдаа гарлаа. Дахин оролдоно уу.', 'assistant');
        }

        statusSpan.textContent = 'Бэлэн байна';

    } catch (error) {
        console.error('Error:', error);
        addMessage('Серверт холбогдоход алдаа гарлаа. Дахин оролдоно уу.', 'assistant');
        statusSpan.textContent = 'Алдаа';
    } finally {
        setFormEnabled(true);
        showLoading(false);
        userInput.focus();
    }
}

// Add message to chat with CoT enhancement detection
function addMessage(content, sender, data = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    avatarDiv.textContent = sender === 'user' ? '👤' : '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Check if this is a CoT-enhanced response
    if (data.cot_enhanced) {
        contentDiv.classList.add('cot-enhanced');

        // Add CoT badge
        const cotBadge = document.createElement('div');
        cotBadge.className = 'cot-badge';
        cotBadge.textContent = '🧠 Chain-of-Thought Enhanced';
        contentDiv.appendChild(cotBadge);
    }

    // Process content for CoT formatting
    if (content.includes('**Дэлгэрэнгүй шинжилгээний алхмууд:**')) {
        formatCotContent(content, contentDiv);
    } else if (content.includes('**Тайлан авах уу?**')) {
        // Split content at the report offer
        const parts = content.split('**Тайлан авах уу?**');

        // Add the main content
        const mainContent = parts[0].replace(/\n/g, '<br>');
        contentDiv.innerHTML += mainContent;

        // Add the report offer box
        const reportOfferDiv = document.createElement('div');
        reportOfferDiv.className = 'report-offer';
        reportOfferDiv.innerHTML = `
            <strong>📋 Тайлан авах уу?</strong>
            ${parts[1].replace(/\n/g, '<br>')}
            <div class="report-buttons">
                <button class="report-button accept" onclick="sendMessage('Тиймээ')">Тиймээ, тайлан авъя</button>
                <button class="report-button decline" onclick="sendMessage('Үгүй, баярлалаа')">Үгүй, баярлалаа</button>
            </div>
        `;
        contentDiv.appendChild(reportOfferDiv);
    } else {
        // Format content with line breaks
        const formattedContent = content.replace(/\n/g, '<br>');
        contentDiv.innerHTML += formattedContent;
    }

    // Add download link if report was generated
    if (data.download_url) {
        const downloadDiv = document.createElement('div');
        downloadDiv.style.marginTop = '10px';

        const downloadLink = document.createElement('a');
        downloadLink.href = data.download_url;
        downloadLink.className = 'download-link';
        downloadLink.textContent = '📥 PDF Тайлан татаж авах';
        downloadLink.target = '_blank';

        downloadDiv.appendChild(downloadLink);
        contentDiv.appendChild(downloadDiv);
    }

    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Format Chain-of-Thought content
function formatCotContent(content, container) {
    const sections = content.split('\n\n');

    sections.forEach(section => {
        if (section.includes('**Дэлгэрэнгүй шинжилгээний алхмууд:**')) {
            const title = document.createElement('h3');
            title.style.color = '#2c3e50';
            title.style.marginBottom = '10px';
            title.textContent = '🧠 Дэлгэрэнгүй шинжилгээний алхмууд:';
            container.appendChild(title);
        } else if (section.includes('**') && section.includes('.')) {
            // This is a thinking step
            const stepDiv = document.createElement('div');
            stepDiv.className = 'thinking-step';

            const lines = section.split('\n');
            const title = lines[0].replace(/\*\*/g, '');
            const content = lines.slice(1).join(' ');

            stepDiv.innerHTML = `
                <div class="step-title">${title}</div>
                <div>${content}</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${Math.random() * 40 + 60}%"></div>
                </div>
            `;
            container.appendChild(stepDiv);
        } else if (section.includes('**Гол дүгнэлтүүд:**')) {
            const insightsDiv = document.createElement('div');
            insightsDiv.className = 'key-insights';
            insightsDiv.innerHTML = '<strong>🔍 Гол дүгнэлтүүд:</strong>';

            const insights = section.split('•').slice(1);
            insights.forEach(insight => {
                if (insight.trim()) {
                    const insightDiv = document.createElement('div');
                    insightDiv.className = 'insight-item';
                    insightDiv.textContent = insight.trim();
                    insightsDiv.appendChild(insightDiv);
                }
            });

            container.appendChild(insightsDiv);
        } else if (section.trim()) {
            const paraDiv = document.createElement('div');
            paraDiv.innerHTML = section.replace(/\n/g, '<br>').replace(/\*\*/g, '<strong>').replace(/\*\*/g, '</strong>');
            paraDiv.style.marginBottom = '10px';
            container.appendChild(paraDiv);
        }
    });
}

// Quick message function
function sendQuickMessage(message) {
    sendMessage(message);
}

// Set form enabled/disabled
function setFormEnabled(enabled) {
    sendButton.disabled = !enabled;
    userInput.disabled = !enabled;
}

// Show/hide loading
function showLoading(show) {
    loading.classList.toggle('active', show);
}

// Refresh cache function
async function refreshCache() {
    try {
        statusSpan.textContent = 'Мэдээлэл шинэчилж байна...';
        cacheStatusSpan.textContent = 'Шинэчилж байна...';

        const response = await fetch('/cache/refresh', { method: 'POST' });
        const data = await response.json();

        if (data.status === 'success') {
            cacheStatusSpan.textContent = 'Кэш: Шинэчлэгдсэн';
            addMessage('✅ Дүүргийн мэдээлэл амжилттай шинэчлэгдлээ!', 'assistant');
        } else {
            cacheStatusSpan.textContent = 'Кэш: Алдаа';
            addMessage('❌ Мэдээлэл шинэчлэхэд алдаа гарлаа.', 'assistant');
        }

        statusSpan.textContent = 'Бэлэн байна';
    } catch (error) {
        console.error('Cache refresh error:', error);
        cacheStatusSpan.textContent = 'Кэш: Алдаа';
        statusSpan.textContent = 'Алдаа';
    }
}

// Show Chain-of-Thought statistics
async function showCotStats() {
    try {
        const response = await fetch('/cot/stats');
        const data = await response.json();

        if (data.status === 'success') {
            const stats = data.cot_stats;
            const features = data.features;

            let statsMessage = `🧠 **Chain-of-Thought Statistics:**\n\n`;
            statsMessage += `📊 Available Analysis Types: ${stats.available_templates}\n`;
            statsMessage += `🔧 Analysis Types: ${stats.analysis_types.join(', ')}\n\n`;
            statsMessage += `✨ **Features:**\n`;
            statsMessage += `• Systematic Reasoning: ${features.systematic_reasoning ? '✅' : '❌'}\n`;
            statsMessage += `• Confidence Scoring: ${features.confidence_scoring ? '✅' : '❌'}\n`;
            statsMessage += `• Step-by-step Analysis: ${features.step_by_step_analysis ? '✅' : '❌'}\n`;
            statsMessage += `• Key Insights Extraction: ${features.key_insights_extraction ? '✅' : '❌'}\n`;
            statsMessage += `• Multi-domain Analysis: ${features.multi_domain_analysis ? '✅' : '❌'}\n`;

            addMessage(statsMessage, 'assistant', { cot_enhanced: true });
        } else {
            addMessage('❌ Chain-of-Thought статистик авахад алдаа гарлаа.', 'assistant');
        }
    } catch (error) {
        console.error('CoT stats error:', error);
        addMessage('❌ Chain-of-Thought статистик авахад алдаа гарлаа.', 'assistant');
    }
}

// Check initial status
async function checkStatus() {
    try {
        const [healthResponse, cacheResponse] = await Promise.all([
            fetch('/health'),
            fetch('/cache/status')
        ]);

        const healthData = await healthResponse.json();
        const cacheData = await cacheResponse.json();

        if (healthData.all_ready) {
            statusSpan.textContent = '🧠 Бэлэн байна (CoT идэвхтэй)';
        } else {
            statusSpan.textContent = 'Эхлүүлж байна...';
        }

        if (cacheData.status === 'success' && cacheData.cache.is_fresh) {
            cacheStatusSpan.textContent = `Кэш: Шинэ (${cacheData.cache.age_days || 0} өдөр)`;
        } else {
            cacheStatusSpan.textContent = 'Кэш: Хуучирсан';
        }

    } catch (error) {
        console.error('Status check error:', error);
        statusSpan.textContent = 'Алдаа';
        cacheStatusSpan.textContent = 'Кэш: Тодорхойгүй';
    }
}

// Initialize
checkStatus();
userInput.focus();

// Periodic status check
setInterval(checkStatus, 30000); // Check every 30 seconds