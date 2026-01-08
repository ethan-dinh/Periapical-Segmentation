# TODO LIST

Below is a list of tasks that need to be completed for the periapical radiograph analysis pipeline.

- [ ] Determine if the images need to be normalized. Right now, they are all differing in terms of width and height. I need to know how if I can train the ROI detection model on images of different sizes.
- [ ] Create a sub directory within ROI Detection for manually creating a model that is designed to detect new ROIs: `alveolar crest`, `periodontal ligament space`, and `lamina dura`.
- [ ] Investigate different ways to enhance the image quality while preserving the anatomical boundaries. If anything I want a method that enhances the model's ability to not only detect the ROIs but also segment the regions of interest.
- [ ] Research different ways to create a model that can predict the alveolar bone crest curvature lines. I have the training data available, I just need to know how to create a model that can predict the curvature lines. Is it better to predict from the entire image or just the alveolar bone ROI?
