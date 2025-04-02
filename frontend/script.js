const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const status = document.getElementById('status');
const patternList = document.getElementById('pattern-list');
const exampleInput = document.getElementById('example-input');
const outputInput = document.getElementById('output-input');
const addPatternBtn = document.getElementById('add-pattern-btn');

dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFileUpload(e.target.files[0]);
    }
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'green';
});

dropZone.addEventListener('dragleave', () => {
    dropZone.style.borderColor = '#ccc';
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '#ccc';
    if (e.dataTransfer.files.length) {
        handleFileUpload(e.dataTransfer.files[0]);
    }
});

function handleFileUpload(file) {
    previewPDF(file).then(() => {
        uploadFile(file);
    });
}

function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    status.innerText = 'Processing...';

    const progressBar = document.getElementById('progress-bar');
    const segments = Array.from(progressBar.getElementsByClassName('progress-segment'));

    const reader = new FileReader();
    reader.onload = function () {
        fetch('http://localhost:8000/upload/stream', {
            method: 'POST',
            body: formData
        });

        const source = new EventSource('http://localhost:8000/progress');
        source.onmessage = function (event) {
            if (event.data === 'done') {
                source.close();
                status.innerText = 'Download complete.';
                fetch('http://localhost:8000/download')
                  .then(response => response.blob())
                  .then(blob => {
                      const url = window.URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.style.display = 'none';
                      a.href = url;
                      a.download = 'processed.zip';
                      document.body.appendChild(a);
                      a.click();
                      window.URL.revokeObjectURL(url);
                  });
            } else {
                const i = parseInt(event.data);
                if (!isNaN(i) && segments[i]) {
                    segments[i].classList.add('done');
                }
            }
        };
    };
    reader.readAsArrayBuffer(file);
}


function previewPDF(file) {
    return new Promise((resolve) => {
        const previewContainer = document.getElementById('pdf-preview');
        const progressBar = document.getElementById('progress-bar');
        previewContainer.innerHTML = '';
        progressBar.innerHTML = '';

        const fileReader = new FileReader();
        fileReader.onload = function () {
            const typedarray = new Uint8Array(this.result);
            pdfjsLib.getDocument(typedarray).promise.then(pdf => {
                const totalPages = pdf.numPages;

                for (let i = 0; i < totalPages; i++) {
                    const segment = document.createElement('div');
                    segment.className = 'progress-segment';
                    progressBar.appendChild(segment);
                }

                let pagesRendered = 0;
                for (let pageNum = 1; pageNum <= totalPages; pageNum++) {
                    pdf.getPage(pageNum).then(page => {
                        const viewport = page.getViewport({ scale: 0.5 });
                        const canvas = document.createElement('canvas');
                        canvas.className = 'pdf-page';
                        const context = canvas.getContext('2d');
                        canvas.height = viewport.height;
                        canvas.width = viewport.width;
                        page.render({ canvasContext: context, viewport: viewport }).promise.then(() => {
                            pagesRendered++;
                            if (pagesRendered === totalPages) {
                                resolve();
                            }
                        });
                        previewContainer.appendChild(canvas);
                    });
                }
            });
        };
        fileReader.readAsArrayBuffer(file);
    });
}

function loadPatterns() {
    fetch('http://localhost:8000/patterns.json')
        .then(response => response.json())
        .then(patterns => {
            patternList.innerHTML = '';
            patterns.forEach((pat) => {
                const item = document.createElement('li');
                item.textContent = `/${pat.regex}/ → ${pat.rename}`;
                patternList.appendChild(item);
            });
        });
}

addPatternBtn.addEventListener('click', () => {
    const example = exampleInput.value.trim();
    const output = outputInput.value.trim();
    if (!example || !output) return;

    fetch('http://localhost:8000/save_pattern_example', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ example, output })
    }).then(() => {
        exampleInput.value = '';
        outputInput.value = '';
        loadPatterns();
    });
});

loadPatterns();
