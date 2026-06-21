/* ============================================
   CareerAI Pro — Main JavaScript
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {

    // ==========================================
    // Particle Canvas Background
    // ==========================================
    const canvas = document.getElementById('particle-canvas');
    const ctx = canvas.getContext('2d');
    let particles = [];
    let animationId;

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    function createParticles() {
        particles = [];
        const count = Math.min(60, Math.floor((canvas.width * canvas.height) / 18000));
        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                radius: Math.random() * 1.5 + 0.5,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3,
                opacity: Math.random() * 0.4 + 0.1
            });
        }
    }

    function drawParticles() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        particles.forEach((p, i) => {
            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0) p.x = canvas.width;
            if (p.x > canvas.width) p.x = 0;
            if (p.y < 0) p.y = canvas.height;
            if (p.y > canvas.height) p.y = 0;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(99, 102, 241, ${p.opacity})`;
            ctx.fill();

            // Connect nearby particles
            for (let j = i + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const dx = p.x - p2.x;
                const dy = p.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 120) {
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.strokeStyle = `rgba(99, 102, 241, ${0.06 * (1 - dist / 120)})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        });

        animationId = requestAnimationFrame(drawParticles);
    }

    resizeCanvas();
    createParticles();
    drawParticles();

    window.addEventListener('resize', () => {
        resizeCanvas();
        createParticles();
    });

    // ==========================================
    // DOM References
    // ==========================================
    const form = document.getElementById('analyzer-form');
    const fileInput = document.getElementById('resume-upload');
    const fileUploadWrapper = document.getElementById('file-upload-wrapper');
    const fileNameDisplay = document.getElementById('file-name-display');
    const submitBtn = document.getElementById('analyze-btn');
    const btnText = submitBtn.querySelector('.btn-text');
    const loader = document.getElementById('loader');
    const heroSection = document.getElementById('hero-section');
    const loadingSection = document.getElementById('loading-section');
    const resultsSection = document.getElementById('results-section');
    const errorMessage = document.getElementById('error-message');
    let lastAnalysisData = null;

    // ==========================================
    // File Input Handler
    // ==========================================
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            fileNameDisplay.textContent = e.target.files[0].name;
            fileUploadWrapper.classList.add('file-selected');
        } else {
            fileNameDisplay.textContent = '';
            fileUploadWrapper.classList.remove('file-selected');
        }
    });

    // ==========================================
    // Loading Step Animation
    // ==========================================
    let loadingStepTimer = null;

    function startLoadingSteps() {
        const steps = ['step-ats', 'step-improve', 'step-interview', 'step-skills', 'step-career'];
        let current = 0;

        // Reset all steps
        steps.forEach(id => {
            const el = document.getElementById(id);
            el.classList.remove('active', 'done');
        });
        document.getElementById(steps[0]).classList.add('active');

        loadingStepTimer = setInterval(() => {
            if (current < steps.length) {
                document.getElementById(steps[current]).classList.remove('active');
                document.getElementById(steps[current]).classList.add('done');
            }
            current++;
            if (current < steps.length) {
                document.getElementById(steps[current]).classList.add('active');
            } else {
                clearInterval(loadingStepTimer);
            }
        }, 1200);
    }

    function stopLoadingSteps() {
        if (loadingStepTimer) {
            clearInterval(loadingStepTimer);
            loadingStepTimer = null;
        }
        // Mark all done
        ['step-ats', 'step-improve', 'step-interview', 'step-skills', 'step-career'].forEach(id => {
            const el = document.getElementById(id);
            el.classList.remove('active');
            el.classList.add('done');
        });
    }

    // ==========================================
    // Form Submission
    // ==========================================
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Hide previous results / errors
        resultsSection.style.display = 'none';
        errorMessage.style.display = 'none';

        // Show loading
        loadingSection.style.display = 'block';
        loadingSection.style.animation = 'fadeInUp 0.4s ease-out';
        startLoadingSteps();

        // Button loading state
        btnText.style.display = 'none';
        loader.style.display = 'block';
        submitBtn.disabled = true;

        const formData = new FormData(form);

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Something went wrong during analysis.');
            }

            stopLoadingSteps();

            // Small delay for the "all done" effect
            await new Promise(r => setTimeout(r, 600));

            displayResults(data);

        } catch (error) {
            console.error('Error:', error);
            errorMessage.textContent = error.message;
            errorMessage.style.display = 'block';
        } finally {
            loadingSection.style.display = 'none';
            btnText.style.display = 'flex';
            loader.style.display = 'none';
            submitBtn.disabled = false;
        }
    });

    // ==========================================
    // Tab Controller
    // ==========================================
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;

            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            tabPanels.forEach(panel => {
                panel.classList.remove('active');
                if (panel.id === `panel-${target}`) {
                    panel.classList.add('active');
                    panel.style.animation = 'fadeInUp 0.4s ease-out';
                }
            });
        });
    });

    // ==========================================
    // Display Results (master function)
    // ==========================================
    function displayResults(data) {
        lastAnalysisData = data;
        renderATSScore(data);
        renderImprovements(data);
        renderInterview(data);
        renderSkillGap(data);
        renderCareerInsights(data);

        // Show results, scroll into view
        resultsSection.style.display = 'block';
        resultsSection.style.animation = 'fadeInUp 0.5s ease-out';

        // Activate ATS tab by default
        tabBtns.forEach(b => b.classList.remove('active'));
        document.getElementById('tab-btn-ats').classList.add('active');
        tabPanels.forEach(p => p.classList.remove('active'));
        document.getElementById('panel-ats').classList.add('active');

        // Smooth scroll to results
        setTimeout(() => {
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }

    // ==========================================
    // ATS Score Renderer
    // ==========================================
    function renderATSScore(data) {
        let score = 0;
        if (typeof data.ats_score === 'number') {
            score = data.ats_score;
        } else if (typeof data.ats_score === 'string') {
            const match = data.ats_score.match(/\d+/);
            if (match) score = parseInt(match[0], 10);
        }

        // Animate SVG gauge
        const gaugeFill = document.getElementById('gauge-fill');
        const gaugeText = document.getElementById('gauge-score-text');
        const circumference = 2 * Math.PI * 85; // r=85
        const offset = circumference - (score / 100) * circumference;

        setTimeout(() => {
            gaugeFill.style.strokeDashoffset = offset;
        }, 100);

        // Animate score number
        animateNumber(gaugeText, 0, score, 1500);

        // Grade label
        const gradeEl = document.getElementById('gauge-grade');
        gradeEl.className = 'gauge-grade';
        if (score >= 80) {
            gradeEl.textContent = 'Excellent Match';
            gradeEl.classList.add('excellent');
        } else if (score >= 65) {
            gradeEl.textContent = 'Good Match';
            gradeEl.classList.add('good');
        } else if (score >= 45) {
            gradeEl.textContent = 'Fair Match';
            gradeEl.classList.add('fair');
        } else {
            gradeEl.textContent = 'Needs Improvement';
            gradeEl.classList.add('poor');
        }

        // Breakdown bars
        const breakdown = data.ats_breakdown || {};
        const categories = ['keywords', 'formatting', 'experience', 'education', 'skills'];

        categories.forEach((cat, index) => {
            const value = breakdown[cat] || 0;
            const valueEl = document.getElementById(`bd-${cat}`);
            const fillEl = document.getElementById(`bf-${cat}`);

            if (valueEl) valueEl.textContent = `${value}%`;
            if (fillEl) {
                setTimeout(() => {
                    fillEl.style.width = `${value}%`;
                }, 200 + index * 150);
            }
        });
    }

    // ==========================================
    // Improvements Renderer
    // ==========================================
    function renderImprovements(data) {
        const list = document.getElementById('improvements-list');
        list.innerHTML = '';

        const improvements = data.improvements || [];

        improvements.forEach((item, index) => {
            const card = document.createElement('div');
            const priorityClass = `priority-${item.priority || 'important'}`;
            card.className = `improvement-card ${priorityClass}`;
            card.style.animationDelay = `${index * 0.08}s`;
            card.dataset.priority = item.priority || 'important';

            const badgeClass = `badge-${item.priority || 'important'}`;
            const badgeText = (item.priority || 'important').replace(/-/g, ' ');

            card.innerHTML = `
                <div class="improvement-badge ${badgeClass}">${badgeText}</div>
                <div class="improvement-content">
                    <h4>${escapeHtml(item.title || 'Suggestion')}</h4>
                    <p>${escapeHtml(item.description || '')}</p>
                    <span class="improvement-category">${escapeHtml(item.category || '')}</span>
                </div>
            `;

            list.appendChild(card);
        });

        // Filter buttons
        const filterBtns = document.querySelectorAll('.filter-btn');
        filterBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                const filter = btn.dataset.filter;
                const cards = list.querySelectorAll('.improvement-card');

                cards.forEach(card => {
                    if (filter === 'all' || card.dataset.priority === filter) {
                        card.style.display = 'flex';
                    } else {
                        card.style.display = 'none';
                    }
                });
            });
        });
    }

    // ==========================================
    // Interview Questions Renderer
    // ==========================================
    function renderInterview(data) {
        const list = document.getElementById('questions-list');
        list.innerHTML = '';

        const questions = data.interview_questions || [];

        questions.forEach((item, index) => {
            const card = document.createElement('div');
            card.className = 'question-card';
            card.style.animationDelay = `${index * 0.08}s`;

            const difficultyClass = `tag-${item.difficulty || 'medium'}`;

            card.innerHTML = `
                <div class="question-header">
                    <div class="question-number">${index + 1}</div>
                    <div class="question-main">
                        <h4>${escapeHtml(item.question || '')}</h4>
                        <div class="question-tags">
                            <span class="question-tag tag-category">${escapeHtml(item.category || 'general')}</span>
                            <span class="question-tag ${difficultyClass}">${escapeHtml(item.difficulty || 'medium')}</span>
                        </div>
                    </div>
                    <svg class="question-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                    </svg>
                </div>
                <div class="question-answer">
                    <div class="answer-content">
                        <span class="answer-label">💡 Preparation Tips</span>
                        <p>${escapeHtml(item.tips || 'No tips available.')}</p>
                    </div>
                </div>
            `;

            // Accordion toggle
            const header = card.querySelector('.question-header');
            header.addEventListener('click', () => {
                card.classList.toggle('open');
            });

            list.appendChild(card);
        });
    }

    // ==========================================
    // Skill Gap Renderer
    // ==========================================
    function renderSkillGap(data) {
        const matchedList = document.getElementById('matched-skills');
        const missingList = document.getElementById('missing-skills');
        matchedList.innerHTML = '';
        missingList.innerHTML = '';

        const skillGap = data.skill_gap || {};

        // Matched skills with proficiency bars
        const matched = skillGap.matched_skills || [];
        matched.forEach((skill, index) => {
            const item = document.createElement('div');
            item.className = 'skill-item';
            item.style.animationDelay = `${index * 0.1}s`;

            item.innerHTML = `
                <div class="skill-header">
                    <span class="skill-name">${escapeHtml(skill.name)}</span>
                    <span class="skill-value">${skill.proficiency}%</span>
                </div>
                <div class="skill-bar">
                    <div class="skill-bar-fill" data-width="${skill.proficiency}"></div>
                </div>
            `;

            matchedList.appendChild(item);
        });

        // Missing skills with recommendations
        const missing = skillGap.missing_skills || [];
        missing.forEach((skill, index) => {
            const item = document.createElement('div');
            item.className = 'missing-skill-item';
            item.style.animationDelay = `${index * 0.1}s`;

            const importanceClass = `importance-${skill.importance || 'medium'}`;

            item.innerHTML = `
                <div class="missing-skill-header">
                    <span class="skill-name">${escapeHtml(skill.name)}</span>
                    <span class="importance-tag ${importanceClass}">${escapeHtml(skill.importance || 'medium')}</span>
                </div>
                <p class="missing-skill-rec">${escapeHtml(skill.recommendation || '')}</p>
            `;

            missingList.appendChild(item);
        });

        // Animate skill bars after a short delay
        setTimeout(() => {
            document.querySelectorAll('.skill-bar-fill').forEach(bar => {
                const width = bar.dataset.width || 0;
                bar.style.width = `${width}%`;
            });
        }, 300);
    }

    // ==========================================
    // Career Insights Renderer
    // ==========================================
    function renderCareerInsights(data) {
        const insights = data.career_insights || {};

        // Role fit gauge
        const fitScore = insights.role_fit || 0;
        const fitFill = document.getElementById('fit-gauge-fill');
        const fitText = document.getElementById('fit-score-text');
        const fitCircumference = 2 * Math.PI * 60; // r=60

        const fitOffset = fitCircumference - (fitScore / 100) * fitCircumference;
        setTimeout(() => {
            fitFill.style.strokeDashoffset = fitOffset;
        }, 100);
        animateNumber(fitText, 0, fitScore, 1500);

        // Strengths
        const strengthsList = document.getElementById('strengths-list');
        strengthsList.innerHTML = '';
        (insights.strengths || []).forEach(s => {
            const li = document.createElement('li');
            li.textContent = s;
            strengthsList.appendChild(li);
        });

        // Growth areas
        const growthList = document.getElementById('growth-list');
        growthList.innerHTML = '';
        (insights.growth_areas || []).forEach(g => {
            const li = document.createElement('li');
            li.textContent = g;
            growthList.appendChild(li);
        });

        // Trajectory
        document.getElementById('trajectory-text').textContent = insights.career_trajectory || 'No trajectory data available.';

        // Salary context
        document.getElementById('salary-text').textContent = insights.salary_context || 'No salary context available.';
    }

    // ==========================================
    // Utility Functions
    // ==========================================
    function animateNumber(element, start, end, duration) {
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + (end - start) * eased);

            element.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ==========================================
    // PDF Download
    // ==========================================
    const downloadBtn = document.getElementById('download-pdf-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            if (!lastAnalysisData) {
                alert('No analysis data available to download. Please run the analysis first.');
                return;
            }

            console.log('[PDF] Starting PDF generation...');
            console.log('[PDF] Analysis data keys:', Object.keys(lastAnalysisData));

            // Validate critical data fields before proceeding
            const data = lastAnalysisData;
            if (typeof data.ats_score === 'undefined' || data.ats_score === null) {
                console.error('[PDF] Missing ats_score in analysis data');
                alert('Analysis data is incomplete (missing ATS score). Please re-run the analysis.');
                return;
            }
            if (!data.skill_gap || !data.career_insights) {
                console.error('[PDF] Missing skill_gap or career_insights in analysis data');
                alert('Analysis data is incomplete. Please re-run the analysis.');
                return;
            }

            // Change button state to loading
            const originalText = downloadBtn.innerHTML;
            downloadBtn.innerHTML = `
                <span style="display: flex; align-items: center; gap: 8px; justify-content: center;">
                    <span class="loader" style="width: 14px; height: 14px; border-width: 2px; border-color: currentColor transparent transparent transparent; display: inline-block; animation: spin 1s linear infinite;"></span>
                    Generating Report...
                </span>
            `;
            downloadBtn.disabled = true;

            // =====================================================
            // FIX: Send data to the new server-side PDF generator
            // instead of using html2pdf.js which creates blank pages
            // =====================================================
            fetch('/download-report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(lastAnalysisData)
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.blob();
            })
            .then(blob => {
                console.log('[PDF] PDF received from server successfully.');
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                // Generate a filename with current date
                const dateStr = new Date().toISOString().slice(0, 10);
                a.download = `CareerAI_Report_${dateStr}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                downloadBtn.innerHTML = originalText;
                downloadBtn.disabled = false;
            })
            .catch(error => {
                console.error('[PDF] Error downloading PDF:', error);
                downloadBtn.innerHTML = originalText;
                downloadBtn.disabled = false;
                alert('Failed to download PDF. Please try again. Check the browser console for details.');
            });
        });
    }

    // ==========================================
    // New Analysis Button
    // ==========================================
    const newAnalysisBtn = document.getElementById('new-analysis-btn');
    if (newAnalysisBtn) {
        newAnalysisBtn.addEventListener('click', () => {
            resultsSection.style.display = 'none';
            errorMessage.style.display = 'none';

            // Reset form
            form.reset();
            fileNameDisplay.textContent = '';
            fileUploadWrapper.classList.remove('file-selected');

            // Reset gauge
            const gaugeFill = document.getElementById('gauge-fill');
            if (gaugeFill) gaugeFill.style.strokeDashoffset = '534';
            const gaugeText = document.getElementById('gauge-score-text');
            if (gaugeText) gaugeText.textContent = '0';

            // Reset fit gauge
            const fitFill = document.getElementById('fit-gauge-fill');
            if (fitFill) fitFill.style.strokeDashoffset = '377';
            const fitText = document.getElementById('fit-score-text');
            if (fitText) fitText.textContent = '0';

            // Reset breakdown bars
            document.querySelectorAll('.breakdown-fill').forEach(bar => {
                bar.style.width = '0%';
            });

            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

});
