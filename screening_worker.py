"""
Worker threads for the screening module.
"""

from PySide6.QtCore import QThread, Signal


class _InferenceWorker(QThread):
    """Run model_inference.run_inference() on a background thread."""
    result_ready = Signal(str, str)      # label, confidence_text
    finished   = Signal(str, str, str)  # label, confidence_text, heatmap_path
    error      = Signal(str)            # hard error message
    ungradable = Signal(str)            # image quality / gradability failure

    def __init__(self, image_path: str):
        super().__init__()
        self._image_path = image_path

    def run(self):
        try:
            from model_inference import generate_heatmap, predict_image, ImageUngradableError
            try:
                label, conf, class_idx = predict_image(self._image_path)
                self.result_ready.emit(label, conf)
                heatmap_path = generate_heatmap(self._image_path, class_idx)
                self.finished.emit(label, conf, heatmap_path)
            except ImageUngradableError as exc:
                self.ungradable.emit(str(exc))
        except Exception as exc:
            self.error.emit(str(exc))
