import torch
import onnxruntime
from onnx import numpy_helper
from PIL import Image
from torchvision import transforms

import numpy as np
import os
import urllib

#           GitHub Repo    |    Model   
MODELS = [
    ('pytorch/vision:v0.5.0', 'shufflenet_v2_x0_5'),
    ('pytorch/vision:v0.5.0', 'shufflenet_v2_x1_0'),
]
data_dir = 'test_data_set_0'

url, filename = ("https://github.com/pytorch/hub/raw/master/dog.jpg", "dog.jpg")
urllib.URLopener().retrieve(url, filename)


def save_tensor_proto(file_path, name, data):
    tp = numpy_helper.from_array(data)
    tp.name = name

    with open(file_path, 'wb') as f:
        f.write(tp.SerializeToString())


def save_data(test_data_dir, prefix, data_list):
    if isinstance(data_list, torch.autograd.Variable) or isinstance(data_list, torch.Tensor):
        data_list = [data_list]
    for i, d in enumerate(data_list):
        d = d.data.cpu().numpy()
        save_tensor_proto(os.path.join(test_data_dir, '{0}_{1}.pb'.format(prefix, i)), prefix + str(i+1), d)


def save(name, model, inputs, outputs, input_names=['input'], output_names=['output'], **kwargs):
    if hasattr(model, 'train'):
        model.train(False)
    dir = './'
    if not os.path.exists(dir):
        os.makedirs(dir)
    dir = os.path.join(dir, 'test_' + name)
    if not os.path.exists(dir):
        os.makedirs(dir)

    def make_list(t):
        return [make_list(i) for i in t] if isinstance(t, (list, tuple)) else t

    def update_list(t, res):
        for i in t:
            res.append(i) if not isinstance(i, (list, tuple)) else update_list(i, res)
        return res

    model_dir = os.path.join(dir, 'model.onnx')
    if isinstance(model, torch.jit.ScriptModule):
        torch.onnx._export(model, inputs, model_dir, verbose=True, input_names=input_names,
                           output_names=output_names, example_outputs=outputs, **kwargs)
    else:
        torch.onnx.export(model, inputs, model_dir, verbose=True, input_names=input_names,
                          output_names=output_names, example_outputs=outputs, **kwargs)

    test_data_dir = os.path.join(dir, data_dir)
    if not os.path.exists(test_data_dir):
        os.makedirs(test_data_dir)

    inputs = make_list(inputs)
    inputs = update_list(inputs, [])
    outputs = make_list(outputs)
    outputs = update_list(outputs, [])

    save_data(test_data_dir, 'input', inputs)
    save_data(test_data_dir, 'output', outputs)

    return model_dir


def to_numpy(tensor):
        return tensor.detach().cpu().numpy() if tensor.requires_grad else tensor.cpu().numpy()


def inference(f, inputs, outputs):
    sess = onnxruntime.InferenceSession(f)
    ort_inputs = {sess.get_inputs()[0].name : to_numpy(inputs)}
    res = sess.run(None, ort_inputs)

    if outputs is not None:
        print("== CHECKING OUTPUT ==")
        all_hidden_states = outputs
        np.testing.assert_allclose(all_hidden_states.detach().numpy(), res[0], rtol=1e-02, atol=1e-05)
        print("== DONE ==")


def shufflenetv2_test():
    for github_repo, model in MODELS:
        # Load pretrained model
        model = torch.hub.load(github_repo, model, pretrained=True)
        model.eval()
        input_image = Image.open(filename)
        preprocess = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        input_tensor = preprocess(input_image)
        input_1 = input_tensor.unsqueeze(0)
        output_1 = model(input_1)

        shufflenetv2 = save('shufflenetv2', model.cpu(), input_1, output_1,
                 opset_version=10,
                 input_names=['input'],
                 output_names=['output'])

        inference(shufflenetv2, input_1, output_1)


shufflenetv2_test()
