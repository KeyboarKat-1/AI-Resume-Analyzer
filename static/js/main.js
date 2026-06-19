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

            // Change button state to loading
            const originalText = downloadBtn.innerHTML;
            downloadBtn.innerHTML = `
                <span style="display: flex; align-items: center; gap: 8px; justify-content: center;">
                    <span class="loader" style="width: 14px; height: 14px; border-width: 2px; border-color: currentColor transparent transparent transparent; display: inline-block; animation: spin 1s linear infinite;"></span>
                    Generating Report...
                </span>
            `;
            downloadBtn.disabled = true;

            const tempContainer = document.createElement('div');
            tempContainer.style.position = 'absolute';
            tempContainer.style.left = '-9999px';
            tempContainer.style.top = '-9999px';
            tempContainer.style.width = '720px';
            tempContainer.style.background = 'white';
            tempContainer.style.padding = '0px';
            tempContainer.style.boxSizing = 'border-box';
            
            const data = lastAnalysisData;
            
            let improvementsHtml = '';
            data.improvements.forEach(imp => {
                let badgeColor = '#fef2f2';
                let borderColor = '#fecaca';
                let textColor = '#991b1b';
                let priorityText = 'Critical';
                if (imp.priority === 'important') {
                    badgeColor = '#fffbeb';
                    borderColor = '#fde68a';
                    textColor = '#92400e';
                    priorityText = 'Important';
                } else if (imp.priority === 'nice-to-have') {
                    badgeColor = '#f0fdf4';
                    borderColor = '#bbf7d0';
                    textColor = '#166534';
                    priorityText = 'Nice to Have';
                }
                improvementsHtml += `
                    <div style="border: 1px solid #e2e8f0; border-left: 4px solid ${textColor}; border-radius: 6px; padding: 12px 15px; background: #f8fafc; margin-bottom: 12px; page-break-inside: avoid;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-size: 13px; font-weight: 700; color: #0f172a;">${escapeHtml(imp.title)}</span>
                            <span style="font-size: 9px; font-weight: 600; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; background: ${badgeColor}; border: 1px solid ${borderColor}; color: ${textColor};">${priorityText}</span>
                        </div>
                        <p style="margin: 0; font-size: 12px; color: #475569; line-height: 1.4;">${escapeHtml(imp.description)}</p>
                        <div style="margin-top: 6px; font-size: 10px; color: #64748b; font-weight: 500; text-transform: uppercase;">Category: ${escapeHtml(imp.category)}</div>
                    </div>
                `;
            });

            let matchedSkillsHtml = '';
            data.skill_gap.matched_skills.forEach(skill => {
                matchedSkillsHtml += `
                    <div style="display: flex; justify-content: space-between; align-items: center; background: white; border: 1px solid #e2e8f0; border-radius: 4px; padding: 6px 10px; margin-bottom: 6px; page-break-inside: avoid;">
                        <span style="font-size: 12px; font-weight: 600; color: #1e293b;">${escapeHtml(skill.name)}</span>
                        <span style="font-size: 11px; font-weight: 700; color: #166534;">${skill.proficiency}%</span>
                    </div>
                `;
            });

            let missingSkillsHtml = '';
            data.skill_gap.missing_skills.forEach(skill => {
                missingSkillsHtml += `
                    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 4px; padding: 8px 10px; margin-bottom: 8px; page-break-inside: avoid;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <span style="font-size: 12px; font-weight: 700; color: #1e293b;">${escapeHtml(skill.name)}</span>
                            <span style="font-size: 9px; font-weight: 600; text-transform: uppercase; padding: 1px 5px; border-radius: 3px; background: ${skill.importance === 'high' ? '#fee2e2' : '#fffbeb'}; color: ${skill.importance === 'high' ? '#991b1b' : '#92400e'};">${skill.importance}</span>
                        </div>
                        <p style="margin: 0; font-size: 11px; color: #475569; line-height: 1.3;">${escapeHtml(skill.recommendation)}</p>
                    </div>
                `;
            });

            let interviewQuestionsHtml = '';
            data.interview_questions.forEach((q, idx) => {
                interviewQuestionsHtml += `
                    <div style="border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 15px; background: #f8fafc; margin-bottom: 12px; page-break-inside: avoid;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">
                            <span style="font-size: 11px; font-weight: 700; color: #475569; text-transform: uppercase;">Question ${idx + 1} (${escapeHtml(q.category)})</span>
                            <span style="font-size: 9px; font-weight: 600; text-transform: uppercase; padding: 1px 5px; border-radius: 3px; background: ${q.difficulty === 'hard' ? '#fee2e2' : q.difficulty === 'medium' ? '#fffbeb' : '#f0fdf4'}; color: ${q.difficulty === 'hard' ? '#991b1b' : q.difficulty === 'medium' ? '#92400e' : '#166534'};">${q.difficulty}</span>
                        </div>
                        <p style="margin: 0 0 8px 0; font-size: 13px; font-weight: 600; color: #0f172a; line-height: 1.4;">"${escapeHtml(q.question)}"</p>
                        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 4px; padding: 8px 10px;">
                            <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 2px;">Preparation Tips:</div>
                            <p style="margin: 0; font-size: 11px; color: #475569; line-height: 1.3;">${escapeHtml(q.tips)}</p>
                        </div>
                    </div>
                `;
            });

            let breakdownRowsHtml = '';
            Object.entries(data.ats_breakdown).forEach(([cat, val]) => {
                breakdownRowsHtml += `
                    <tr style="border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 10px; font-size: 13px; font-weight: 600; text-transform: capitalize; color: #1e293b;">${escapeHtml(cat)}</td>
                        <td style="padding: 10px; width: 60%;">
                            <div style="width: 100%; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;">
                                <div style="width: ${val}%; height: 100%; background: #3b82f6; border-radius: 3px;"></div>
                            </div>
                        </td>
                        <td style="padding: 10px; font-size: 13px; font-weight: 700; text-align: right; color: #0f172a;">${val}%</td>
                    </tr>
                `;
            });

            let strengthsHtml = '';
            data.career_insights.strengths.forEach(str => {
                strengthsHtml += `<li style="margin-bottom: 4px; line-height: 1.4;">${escapeHtml(str)}</li>`;
            });

            let growthHtml = '';
            data.career_insights.growth_areas.forEach(growth => {
                growthHtml += `<li style="margin-bottom: 4px; line-height: 1.4;">${escapeHtml(growth)}</li>`;
            });

            tempContainer.innerHTML = `
                <div style="font-family: 'Inter', system-ui, -apple-system, sans-serif; color: #1e293b; background: white; padding: 30px; line-height: 1.5;">
                    <!-- Header -->
                    <div style="border-bottom: 2px solid #3b82f6; padding-bottom: 12px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: flex-end;">
                        <div>
                            <h1 style="color: #0f172a; margin: 0; font-size: 24px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;">CareerAI Pro</h1>
                            <p style="color: #64748b; margin: 3px 0 0 0; font-size: 12px; font-weight: 500;">AI-Powered Career & Resume Analysis Report</p>
                        </div>
                        <div style="font-size: 11px; color: #94a3b8; font-weight: 500;">Generated on: ${new Date().toLocaleDateString()}</div>
                    </div>

                    <!-- Metrics Grid -->
                    <div style="display: flex; gap: 15px; margin-bottom: 25px;">
                        <div style="flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; background: #f8fafc; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                            <div style="font-size: 11px; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">ATS Match Score</div>
                            <div style="font-size: 40px; font-weight: 800; color: #3b82f6; margin: 5px 0;">${data.ats_score}<span style="font-size: 16px; color: #64748b; font-weight: 500;">/100</span></div>
                            <div style="font-size: 12px; font-weight: 700; color: ${data.ats_score >= 80 ? '#166534' : data.ats_score >= 65 ? '#854d0e' : '#991b1b'};">
                                ${data.ats_score >= 80 ? 'Excellent Match' : data.ats_score >= 65 ? 'Good Match' : data.ats_score >= 45 ? 'Fair Match' : 'Needs Improvement'}
                            </div>
                        </div>
                        <div style="flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; background: #f8fafc; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                            <div style="font-size: 11px; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Role Fit Index</div>
                            <div style="font-size: 40px; font-weight: 800; color: #8b5cf6; margin: 5px 0;">${data.career_insights.role_fit}<span style="font-size: 16px; color: #64748b; font-weight: 500;">/100</span></div>
                            <div style="font-size: 12px; color: #64748b; font-weight: 500;">Relative Candidate Suitability</div>
                        </div>
                    </div>

                    <!-- Category Breakdown -->
                    <div style="margin-bottom: 25px; page-break-inside: avoid;">
                        <h2 style="font-size: 15px; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin: 0 0 12px 0; text-transform: uppercase; letter-spacing: 0.5px;">ATS Category Breakdown</h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tbody>
                                ${breakdownRowsHtml}
                            </tbody>
                        </table>
                    </div>

                    <div style="page-break-before: always;"></div>

                    <!-- Resume Improvements -->
                    <div style="margin-bottom: 25px;">
                        <h2 style="font-size: 15px; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin: 0 0 12px 0; text-transform: uppercase; letter-spacing: 0.5px;">Critical Resume Improvements</h2>
                        <div>
                            ${improvementsHtml}
                        </div>
                    </div>

                    <div style="page-break-before: always;"></div>

                    <!-- Skill Gap Analysis -->
                    <div style="margin-bottom: 25px;">
                        <h2 style="font-size: 15px; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin: 0 0 15px 0; text-transform: uppercase; letter-spacing: 0.5px;">Skill Gap Analysis</h2>
                        <div style="display: flex; gap: 15px;">
                            <div style="flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #f8fafc; min-height: 250px;">
                                <h3 style="font-size: 13px; color: #166534; margin: 0 0 10px 0; border-bottom: 1px solid #dcfce7; padding-bottom: 4px; display: flex; align-items: center; gap: 4px;">
                                    ✓ Matched Skills
                                </h3>
                                <div>
                                    ${matchedSkillsHtml}
                                </div>
                            </div>
                            <div style="flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #f8fafc; min-height: 250px;">
                                <h3 style="font-size: 13px; color: #991b1b; margin: 0 0 10px 0; border-bottom: 1px solid #fee2e2; padding-bottom: 4px; display: flex; align-items: center; gap: 4px;">
                                    ⚠ Skills to Acquire
                                </h3>
                                <div>
                                    ${missingSkillsHtml}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div style="page-break-before: always;"></div>

                    <!-- Predicted Interview Questions -->
                    <div style="margin-bottom: 25px;">
                        <h2 style="font-size: 15px; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin: 0 0 12px 0; text-transform: uppercase; letter-spacing: 0.5px;">Predicted Interview Questions</h2>
                        <div>
                            ${interviewQuestionsHtml}
                        </div>
                    </div>

                    <div style="page-break-before: always;"></div>

                    <!-- Career Insights -->
                    <div style="margin-bottom: 10px;">
                        <h2 style="font-size: 15px; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin: 0 0 12px 0; text-transform: uppercase; letter-spacing: 0.5px;">Career Insights & Development</h2>
                        
                        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #f8fafc; margin-bottom: 15px; page-break-inside: avoid;">
                            <h3 style="font-size: 12px; color: #0f172a; margin: 0 0 6px 0; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">Core Strengths</h3>
                            <ul style="margin: 0; padding-left: 15px; font-size: 12px; color: #334155;">
                                ${strengthsHtml}
                            </ul>
                        </div>

                        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #f8fafc; margin-bottom: 15px; page-break-inside: avoid;">
                            <h3 style="font-size: 12px; color: #0f172a; margin: 0 0 6px 0; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">Primary Development Gaps</h3>
                            <ul style="margin: 0; padding-left: 15px; font-size: 12px; color: #334155;">
                                ${growthHtml}
                            </ul>
                        </div>

                        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #f8fafc; margin-bottom: 15px; page-break-inside: avoid;">
                            <h3 style="font-size: 12px; color: #0f172a; margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 0.5px;">Recommended Path & Trajectory</h3>
                            <p style="margin: 0; font-size: 12px; color: #334155; line-height: 1.4;">${escapeHtml(data.career_insights.career_trajectory)}</p>
                        </div>

                        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #f8fafc; page-break-inside: avoid;">
                            <h3 style="font-size: 12px; color: #0f172a; margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 0.5px;">Earning Potential & Market Value</h3>
                            <p style="margin: 0; font-size: 12px; color: #334155; line-height: 1.4;">${escapeHtml(data.career_insights.salary_context)}</p>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(tempContainer);

            const opt = {
                margin: [10, 10, 10, 10],
                filename: `CareerAI_Analysis_Report_${new Date().toISOString().slice(0, 10)}.pdf`,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2, useCORS: true, backgroundColor: '#ffffff' },
                jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
                pagebreak: { mode: ['css', 'legacy'] }
            };

            html2pdf().set(opt).from(tempContainer).save().then(() => {
                document.body.removeChild(tempContainer);
                downloadBtn.innerHTML = originalText;
                downloadBtn.disabled = false;
            }).catch(err => {
                console.error('Error generating PDF:', err);
                if (tempContainer.parentNode) {
                    document.body.removeChild(tempContainer);
                }
                downloadBtn.innerHTML = originalText;
                downloadBtn.disabled = false;
                alert('Failed to generate PDF. Please try again.');
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
